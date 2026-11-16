"""Data update coordinator and router actions."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TeltonikaApiError,
    TeltonikaAuthError,
    TeltonikaClient,
    TeltonikaConnectionError,
    TeltonikaError,
)
from .const import (
    AP_REFRESH_DELAY,
    CONF_PROBE_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_PROBE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_PORTAL_RESULT,
    METRIC_MOBILE_FIRST,
    METRIC_WIFI_FIRST,
    PORTAL_FIRST_DELAY,
    PORTAL_POLL_INTERVAL,
    PRIORITY_VERIFY_DELAY,
    PROBE_TIMEOUT,
    UPLINK_WIFI,
)
from .models import (
    SAVED_MULTI_AP,
    RouterInfo,
    ScanNetwork,
    TeltonikaData,
    WifiStation,
    build_scan_networks,
    is_modem_online,
    is_protected_interface,
    next_multi_ap_priority,
    normalize_band,
    radio_band,
    radio_occupant,
)

_LOGGER = logging.getLogger(__name__)

type TeltonikaConfigEntry = ConfigEntry[TeltonikaCoordinator]


def _monotonic() -> float:
    """Return the clock used for portal mode deadlines (patched in tests)."""
    return time.monotonic()


@asynccontextmanager
async def translate_errors() -> AsyncIterator[None]:
    """Turn client errors into Home Assistant errors for the UI."""
    try:
        yield
    except TeltonikaAuthError as err:
        raise HomeAssistantError(f"Router login failed: {err}") from err
    except TeltonikaError as err:
        raise HomeAssistantError(str(err)) from err


class TeltonikaCoordinator(DataUpdateCoordinator[TeltonikaData]):
    """Poll one router and run actions on it."""

    config_entry: TeltonikaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TeltonikaConfigEntry,
        client: TeltonikaClient,
        router: RouterInfo,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {router.host}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.router = router
        self.portal_waiting = False
        self._probe_url: str = entry.options.get(CONF_PROBE_URL, DEFAULT_PROBE_URL)
        # State of the Wi-Fi management entities; the password is never stored.
        self.scan_results: list[ScanNetwork] = []
        self.selected_scan: str | None = None
        self.selected_saved: str | None = None
        self.wifi_password = ""
        self.last_action: str | None = None

    @property
    def router_device_info(self) -> DeviceInfo:
        """Return the device registry entry of the router."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.router.unique_id)},
            name=self.router.name,
            manufacturer="Teltonika",
            model=self.router.model,
            serial_number=self.router.serial,
            sw_version=self.router.firmware,
            configuration_url=f"https://{self.router.host}",
        )

    async def _async_update_data(self) -> TeltonikaData:
        client = self.client
        try:
            interfaces, interface_config = await asyncio.gather(
                client.async_interfaces_status(), client.async_interfaces_config()
            )
            optional = await asyncio.gather(
                client.async_wireless_config(),
                client.async_wireless_status(),
                client.async_wireless_devices_status(),
                client.async_modems_status(),
                client.async_gps_status(),
                return_exceptions=True,
            )
        except TeltonikaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TeltonikaError as err:
            raise UpdateFailed(str(err)) from err

        parts: list[Any] = []
        for result in optional:
            if isinstance(result, TeltonikaApiError):
                # Router without Wi-Fi, modem or GPS: the endpoint is missing.
                parts.append([])
            elif isinstance(result, TeltonikaAuthError):
                raise ConfigEntryAuthFailed(str(result)) from result
            elif isinstance(result, TeltonikaConnectionError):
                raise UpdateFailed(str(result)) from result
            elif isinstance(result, BaseException):
                raise UpdateFailed(f"Unexpected error: {result}") from result
            else:
                parts.append(result)
        wireless_config, wireless_status, wireless_devices, modems, gps = parts

        multi_ap: list[dict[str, Any]] = []
        if any(item.get("mode") == "multi_ap" for item in wireless_config):
            try:
                multi_ap = await client.async_multi_ap_config()
            except TeltonikaAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except TeltonikaConnectionError as err:
                raise UpdateFailed(str(err)) from err
            except TeltonikaApiError:
                multi_ap = []

        data = TeltonikaData.build(
            interfaces=interfaces,
            interface_config=interface_config,
            wireless_config=wireless_config,
            wireless_status=wireless_status,
            wireless_devices=wireless_devices,
            modems=modems,
            gps=gps if isinstance(gps, dict) else None,
            multi_ap=multi_ap,
            router_time=client.server_time,
        )
        data.portal_waiting = self.portal_waiting
        if self._probe_url and data.uplink is not None:
            data.internet = await self._async_probe_internet()
        return data

    async def _async_probe_internet(self) -> bool:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                self._probe_url,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=PROBE_TIMEOUT),
            ) as response:
                return response.status == 204
        except (aiohttp.ClientError, TimeoutError):
            return False

    def modem_ids(self) -> list[str]:
        """Return the ids of all modems with a full status."""
        return [
            str(m.get("id"))
            for m in self.data.modems
            if m.get("id") and is_modem_online(m)
        ]

    async def async_restart_mobile(self, modem_id: str) -> None:
        """Re-establish the mobile data connection."""
        async with translate_errors():
            await self.client.async_restart_modem_connection(modem_id)
        await self.async_request_refresh()

    async def async_reconnect_wifi(self) -> None:
        """Reconnect all saved Wi-Fi client networks."""
        stations = self.data.stations
        if not stations:
            raise HomeAssistantError("No saved Wi-Fi network to reconnect")
        async with translate_errors():
            for station in stations:
                await self.client.async_reconnect_wifi(station.config_id)
        await self.async_request_refresh()

    async def async_reboot(self) -> None:
        """Reboot the router."""
        async with translate_errors():
            await self.client.async_reboot()

    async def async_set_access_point(self, config_id: str, enabled: bool) -> None:
        """Switch one of the router's own access points on or off."""
        async with translate_errors():
            await self.client.async_set_wireless_enabled(config_id, enabled)
        await asyncio.sleep(AP_REFRESH_DELAY)
        await self.async_request_refresh()

    async def async_switch_sim(self, modem_id: str, target_sim: int) -> None:
        """Switch a dual SIM modem to the requested slot."""
        modem = self.data.modem(modem_id)
        if modem is None:
            raise HomeAssistantError("Modem not found")
        if int(modem.get("active_sim") or 0) == target_sim:
            return
        async with translate_errors():
            await self.client.async_switch_sim(modem_id)
        await self.async_request_refresh()

    async def _async_apply_metric(
        self, stations: list[WifiStation], metric: str
    ) -> None:
        async with translate_errors():
            for station in stations:
                if station.interface_id:
                    await self.client.async_set_interface_metric(
                        station.interface_id, metric
                    )
                # Reconnect so netifd installs the route with the new metric.
                await self.client.async_reconnect_wifi(station.config_id)

    async def async_set_wifi_priority(
        self, wifi_first: bool, *, verify: bool = False
    ) -> bool:
        """Prefer Wi-Fi or mobile data; optionally roll back without internet."""
        stations = [s for s in self.data.stations if s.interface_id]
        if not stations:
            raise HomeAssistantError("No saved Wi-Fi network with an interface")

        await self._async_apply_metric(
            stations, METRIC_WIFI_FIRST if wifi_first else METRIC_MOBILE_FIRST
        )
        if not (wifi_first and verify):
            await self.async_request_refresh()
            return True

        await asyncio.sleep(PRIORITY_VERIFY_DELAY)
        await self.async_refresh()
        data = self.data
        if data.uplink is not None and data.uplink.kind == UPLINK_WIFI and data.internet:
            return True
        await self._async_apply_metric(stations, METRIC_MOBILE_FIRST)
        await self.async_request_refresh()
        return False

    async def async_scan_wifi(self, radio: str | None = None) -> list[dict[str, Any]]:
        """Scan with one radio or with all radios and return trimmed results."""
        devices = self.data.wireless_devices
        radios = [radio] if radio else [str(d["id"]) for d in devices if d.get("id")]
        if not radios:
            raise HomeAssistantError("No Wi-Fi radio found")

        results: list[dict[str, Any]] = []
        async with translate_errors():
            for radio_id in radios:
                radio_default = radio_band(radio_id, devices)
                for item in await self.client.async_scan_wifi(radio_id):
                    encryption = item.get("encryption")
                    encrypted = bool(
                        encryption.get("enabled")
                        if isinstance(encryption, dict)
                        else encryption
                    )
                    results.append(
                        {
                            "ssid": item.get("ssid"),
                            "bssid": item.get("bssid"),
                            "signal": item.get("signal"),
                            "channel": item.get("channel"),
                            "band": normalize_band(channel=item.get("channel"))
                            or radio_default,
                            "encrypted": encrypted,
                            "security": item.get("encryption_description"),
                            "radio": radio_id,
                        }
                    )
        return results

    async def async_join_wifi(
        self,
        *,
        radio: str,
        ssid: str,
        bssid: str | None = None,
        password: str | None = None,
    ) -> None:
        """Save a network; keep mobile data first so nothing breaks."""
        async with translate_errors():
            wireless_config = await self.client.async_wireless_config()
        occupant = radio_occupant(wireless_config, radio)
        if occupant is not None and occupant.get("mode") == "multi_ap":
            await self._async_save_multi_ap(ssid, password)
            return
        if occupant is not None:
            raise HomeAssistantError(
                f"Radio {radio} already has a Wi-Fi client "
                f"({occupant.get('ssid') or occupant.get('id')}). The router allows "
                "only one client or one Multi AP per radio; remove it first."
            )

        async with translate_errors():
            created = await self.client.async_join_wifi(
                radio=radio, ssid=ssid, bssid=bssid, password=password
            )
        await asyncio.sleep(AP_REFRESH_DELAY)
        await self.async_refresh()

        network = created.get("network")
        station = next(
            (
                s
                for s in self.data.stations
                if (network and s.network == network) or (not network and s.ssid == ssid)
            ),
            None,
        )
        if station is not None and station.interface_id:
            async with translate_errors():
                await self.client.async_set_interface_metric(
                    station.interface_id, METRIC_MOBILE_FIRST
                )
        await self.async_request_refresh()

    async def _async_save_multi_ap(self, ssid: str, password: str | None) -> None:
        """Add a network to the Multi AP list or update its password."""
        async with translate_errors():
            entries = await self.client.async_multi_ap_config()
            existing = next((e for e in entries if e.get("ssid") == ssid), None)
            if existing is None:
                await self.client.async_add_multi_ap(
                    ssid=ssid,
                    password=password,
                    priority=next_multi_ap_priority(entries),
                )
            elif password:
                await self.client.async_update_multi_ap_key(
                    str(existing.get("id")), password
                )
            else:
                raise HomeAssistantError(f"{ssid} is already in the Multi AP list")
        await self.async_request_refresh()

    async def _async_forget_multi_ap(self, ssid: str) -> None:
        async with translate_errors():
            entries = await self.client.async_multi_ap_config()
            ids = [str(e.get("id")) for e in entries if e.get("ssid") == ssid]
            if not ids:
                raise HomeAssistantError(f"{ssid} is not in the Multi AP list")
            # With an empty list the router service multi_wifi restarts every 5 s.
            if len(entries) - len(ids) < 1:
                raise HomeAssistantError(
                    f"{ssid} is the last Multi AP entry and stays: an empty list "
                    "makes the router service restart in a loop. Remove it in the "
                    "router web interface."
                )
            for entry_id in ids:
                await self.client.async_delete_multi_ap(entry_id)
        await self.async_request_refresh()

    async def async_forget_wifi(
        self, config_id: str | None = None, ssid: str | None = None
    ) -> None:
        """Remove a saved Wi-Fi client network or a Multi AP list entry."""
        if ssid is not None:
            await self._async_forget_multi_ap(ssid)
            return
        if config_id is None:
            raise HomeAssistantError("Give a network ID or an SSID")

        station = next((s for s in self.data.stations if s.config_id == config_id), None)
        if station is not None and station.mode == "multi_ap":
            raise HomeAssistantError(
                "Networks of a Multi AP radio are removed by SSID, not by network ID"
            )
        async with translate_errors():
            await self.client.async_delete_wireless(config_id)
            interface_id = station.interface_id if station else None
            if interface_id and not is_protected_interface(interface_id):
                try:
                    await self.client.async_delete_interface(interface_id)
                except TeltonikaApiError as err:
                    _LOGGER.debug("Interface %s not removed: %s", interface_id, err)
        await self.async_request_refresh()

    def _report(self, text: str) -> None:
        """Remember the result of the last Wi-Fi action for the sensor."""
        self.last_action = text
        self.async_update_listeners()

    async def async_scan_networks(self) -> None:
        """Scan with all radios and fill the list of networks that can be added."""
        try:
            found = await self.async_scan_wifi(None)
        except HomeAssistantError as err:
            self._report(f"Scan failed: {err}")
            raise
        networks, seen, hidden = build_scan_networks(found, self.data.saved_networks)
        self.scan_results = networks
        self.selected_scan = networks[0].label if networks else None
        self._report(f"{len(networks)} new networks ({seen} seen, {hidden} already saved)")

    async def async_add_selected_network(self) -> None:
        """Save the selected scan result with the entered password."""
        network = next((n for n in self.scan_results if n.label == self.selected_scan), None)
        if network is None:
            raise HomeAssistantError("Scan for networks and select one first")
        password = self.wifi_password or None
        if network.encrypted and (password is None or len(password) < 8):
            raise HomeAssistantError("Enter the Wi-Fi password (at least 8 characters) first")
        try:
            await self.async_join_wifi(
                radio=network.radio,
                ssid=network.ssid,
                password=password if network.encrypted else None,
            )
        except HomeAssistantError as err:
            self._report(f"{network.ssid} not saved: {err}")
            raise
        self.wifi_password = ""
        self.scan_results = [n for n in self.scan_results if n.label != network.label]
        self.selected_scan = self.scan_results[0].label if self.scan_results else None
        self._report(f"Saved {network.ssid}")

    async def async_remove_selected_network(self) -> None:
        """Remove the selected saved network."""
        saved = next(
            (s for s in self.data.saved_networks if s.label == self.selected_saved), None
        )
        if saved is None:
            raise HomeAssistantError("Select a saved network first")
        try:
            if saved.kind == SAVED_MULTI_AP:
                await self.async_forget_wifi(ssid=saved.ssid)
            else:
                await self.async_forget_wifi(config_id=saved.config_id)
        except HomeAssistantError as err:
            self._report(f"{saved.ssid} not removed: {err}")
            raise
        self.selected_saved = None
        self._report(f"Removed {saved.ssid}")

    async def async_start_portal_mode(self, minutes: int) -> None:
        """Prefer Wi-Fi and wait until the hotspot login page is confirmed."""
        if self.portal_waiting:
            raise HomeAssistantError("Portal mode is already running")
        stations = [s for s in self.data.stations if s.interface_id]
        if not stations:
            raise HomeAssistantError("No saved Wi-Fi network with an interface")
        self.portal_waiting = True
        self.data.portal_waiting = True
        self.async_update_listeners()
        self.config_entry.async_create_background_task(
            self.hass,
            self._async_portal_run(stations, minutes),
            name=f"{DOMAIN}_portal_mode",
        )

    async def _async_portal_run(
        self, stations: list[WifiStation], minutes: int
    ) -> None:
        success = False
        try:
            await self._async_apply_metric(stations, METRIC_WIFI_FIRST)
            deadline = _monotonic() + minutes * 60
            await asyncio.sleep(PORTAL_FIRST_DELAY)
            while True:
                await self.async_refresh()
                uplink = self.data.uplink
                if uplink is not None and uplink.kind == UPLINK_WIFI and self.data.internet:
                    success = True
                    break
                if _monotonic() >= deadline:
                    break
                await asyncio.sleep(PORTAL_POLL_INTERVAL)
            if not success:
                await self._async_apply_metric(stations, METRIC_MOBILE_FIRST)
        except Exception:  # noqa: BLE001 - background task must always clean up
            _LOGGER.exception("Portal mode failed")
        finally:
            self.portal_waiting = False
            self.hass.bus.async_fire(
                EVENT_PORTAL_RESULT,
                {"entry_id": self.config_entry.entry_id, "success": success},
            )
            await self.async_request_refresh()
