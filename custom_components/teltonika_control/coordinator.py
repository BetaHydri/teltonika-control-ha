"""Data update coordinator and router actions."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    TeltonikaApiError,
    TeltonikaAuthError,
    TeltonikaClient,
    TeltonikaConnectionError,
    TeltonikaError,
)
from .const import (
    AP_REFRESH_DELAY,
    CONF_CONFIG_INTERVAL,
    CONF_DATA_PLAN,
    CONF_PROBE_URL,
    CONF_SCAN_INTERVAL,
    CONF_VPN_HOST,
    CONF_VPN_PORT,
    DEFAULT_CONFIG_INTERVAL,
    DEFAULT_PROBE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VPN_PORT,
    DHCP_INTERVAL,
    DOMAIN,
    EVENT_PORTAL_RESULT,
    EVENT_SMS_RECEIVED,
    FIRMWARE_DOWNLOAD_SETTLE,
    FIRMWARE_INSTALL_GRACE,
    FIRMWARE_INSTALL_TIMEOUT,
    FIRMWARE_WATCH_SECONDS,
    GPS_GLITCH_POLLS,
    METRIC_MOBILE_FIRST,
    METRIC_WIFI_FIRST,
    MISSING_PAGE_PAUSE,
    PORT_FORWARD_REFRESH_DELAY,
    PORTAL_FIRST_DELAY,
    PORTAL_POLL_INTERVAL,
    PRIORITY_VERIFY_DELAY,
    PROBE_TIMEOUT,
    ROAMING_REFRESH_DELAY,
    SLOW_PAGE_PAUSE,
    UPLINK_WIFI,
    VPN_FAMILIES,
    VPN_RECONNECT_DELAY,
    VPN_REFRESH_DELAY,
    VPN_TIMEOUT,
)
from .debug import shape_text
from .models import (
    PHONE_NUMBER_HINT,
    SAVED_MULTI_AP,
    FirmwareDownload,
    GpsPosition,
    RouterInfo,
    ScanNetwork,
    TeltonikaData,
    VpnInstance,
    VpnTunnel,
    WifiStation,
    build_scan_networks,
    clean_phone_number,
    derive_installed_firmware,
    is_modem_online,
    is_protected_interface,
    next_multi_ap_priority,
    normalize_band,
    radio_band,
    radio_occupant,
    to_int,
)

_LOGGER = logging.getLogger(__name__)

type TeltonikaConfigEntry = ConfigEntry[TeltonikaCoordinator]

# Router pages: client method and how often the page is read. "status" pages
# change all the time and are read on every update, "config" pages only change
# when someone edits the router and are read after the configuration interval.
PAGES: dict[str, tuple[Any, ...]] = {
    "interface_config": ("async_interfaces_config", "config"),
    "wireless_config": ("async_wireless_config", "config"),
    "wireless_devices": ("async_wireless_devices_status", "config"),
    "wireguard": ("async_wireguard_config", "config"),
    "sim_cards": ("async_sim_cards_config", "config"),
    "port_forwards": ("async_port_forwards_config", "config"),
    "traffic_rules": ("async_traffic_rules_config", "config"),
    "multi_ap": ("async_multi_ap_config", "config"),
    "wireless_status": ("async_wireless_status", "status"),
    "modems": ("async_modems_status", "status"),
    "gps": ("async_gps_status", "status"),
    "usage": ("async_usage_status", "status"),
    "dhcp": ("async_dhcp_leases", "medium"),
    "failover": ("async_failover_status", "medium"),
    "failover_config": ("async_failover_config", "config"),
    "data_limit": ("async_data_limit_status", "medium"),
    "sms": ("async_sms_messages", "medium"),
    "data_usage_day": ("async_data_usage", "medium", "day"),
    "data_usage_month": ("async_data_usage", "medium", "month"),
    "firmware_updates": ("async_firmware_updates", "config"),
    "firmware_progress": ("async_firmware_progress", "medium"),
    "firmware_device": ("async_firmware_device", "config"),
    **{
        f"vpn_{kind.key}_config": ("async_vpn_config", "config", kind.key)
        for kind in VPN_FAMILIES
    },
    **{
        f"vpn_{kind.key}_status": ("async_vpn_status", "medium", kind.key)
        for kind in VPN_FAMILIES
    },
}


def _monotonic() -> float:
    """Return the clock used for portal mode deadlines (patched in tests)."""
    return time.monotonic()


async def _nothing() -> None:
    """Placeholder for a check that is switched off."""
    return None


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
            # No host in the name: Home Assistant writes it into its own log lines.
            name=f"{DOMAIN} {entry.entry_id[:8]}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.router = router
        self.portal_waiting = False
        self._probe_url: str = entry.options.get(CONF_PROBE_URL, DEFAULT_PROBE_URL)
        self.vpn_host: str = entry.options.get(CONF_VPN_HOST, "")
        self._vpn_port: int = entry.options.get(CONF_VPN_PORT, DEFAULT_VPN_PORT)
        # The data plan in gigabytes (1 GB = 10^9 bytes, as providers count);
        # 0 or missing means no plan.
        self._data_plan_bytes: float = (
            float(entry.options.get(CONF_DATA_PLAN) or 0) * 1_000_000_000
        )
        # Last good answer of every page, when it was read, and until when a
        # page that did not answer (or does not exist) is left alone.
        self._last_good: dict[str, Any] = {}
        self._fetched_at: dict[str, float] = {}
        self._slow_until: dict[str, float] = {}
        self._missing_until: dict[str, float] = {}
        # Short text per page for the debug log and the diagnostics download.
        self._page_notes: dict[str, str] = {}
        self._reported = False
        # Keys of the SMS in the inbox at the last reading; None until the
        # first reading, which announces nothing.
        self._sms_seen: set[str] | None = None
        # Last GPS reading with satellites, and how many empty ones came since.
        self._last_fix: dict[str, Any] | None = None
        self._gps_misses = 0
        # The last position that came with a fix survives a restart, so that a
        # parked router without sky view still has a place.
        self._known_store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.gps"
        )
        self._known_position: GpsPosition | None = None
        self._known_at: datetime | None = None
        self._config_interval: float = entry.options.get(
            CONF_CONFIG_INTERVAL, DEFAULT_CONFIG_INTERVAL
        )
        # State of the Wi-Fi management entities; the password is never stored.
        self.scan_results: list[ScanNetwork] = []
        self.selected_scan: str | None = None
        self.selected_saved: str | None = None
        self.wifi_password = ""
        self.last_action: str | None = None
        self.scanning = False
        # The SMS being composed in the text entities, and the result of the last send.
        self.sms_number = ""
        self.sms_text = ""
        self.last_sms: str | None = None
        # While a firmware download runs, its progress is read on every update.
        self._watch_download_until = 0.0
        self._firmware_updates_seen: dict[str, Any] | None = None
        # When the last download was asked for, and whether the router's
        # "succeeded" turned out to belong to a file that is gone.
        self.download_requested_at: float | None = None
        self.stale_download = False
        # An installation we started: when, from which version, and whether it failed.
        self.installing_since: float | None = None
        self._install_from: str | None = None
        self.install_failed = False

    @property
    def router_device_info(self) -> DeviceInfo:
        """Return the device registry entry of the router.

        The MAC addresses link the router to the same device in other
        integrations and let Home Assistant match a discovered router to it.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self.router.unique_id)},
            connections={
                (CONNECTION_NETWORK_MAC, format_mac(mac))
                for mac in (self.router.mac, self.router.mac_eth)
                if mac
            },
            name=self.router.name,
            manufacturer="Teltonika",
            model=self.router.model,
            serial_number=self.router.serial,
            sw_version=self.router.firmware,
            configuration_url=f"https://{self.router.host}",
        )

    async def _async_setup(self) -> None:
        """Load the last known GPS position."""
        stored = await self._known_store.async_load()
        if not isinstance(stored, dict):
            return
        try:
            self._known_position = GpsPosition(
                latitude=float(stored["latitude"]),
                longitude=float(stored["longitude"]),
                altitude=stored.get("altitude"),
                speed=None,
                accuracy=stored.get("accuracy"),
                satellites=stored.get("satellites"),
                heading=None,
                fix_status=None,
            )
            self._known_at = dt_util.parse_datetime(str(stored.get("at")))
        except (KeyError, TypeError, ValueError):
            self._known_position = None
            self._known_at = None

    def _remember_position(self, data: TeltonikaData) -> None:
        """Keep the last position with a fix, and hand it to the snapshot."""
        position = data.gps
        if data.gps_fix and position is not None:
            moved = (
                self._known_position is None
                or abs(position.latitude - self._known_position.latitude) > 0.0001
                or abs(position.longitude - self._known_position.longitude) > 0.0001
            )
            self._known_position = position
            self._known_at = dt_util.utcnow()
            if moved:
                self._known_store.async_delay_save(self._known_snapshot, 120)
        data.gps_last_known = self._known_position
        data.gps_last_fix = self._known_at

    def _known_snapshot(self) -> dict[str, Any]:
        position = self._known_position
        if position is None:
            return {}
        return {
            "latitude": position.latitude,
            "longitude": position.longitude,
            "altitude": position.altitude,
            "accuracy": position.accuracy,
            "satellites": position.satellites,
            "at": self._known_at.isoformat() if self._known_at else None,
        }

    async def _async_update_data(self) -> TeltonikaData:
        client = self.client
        try:
            interfaces = await client.async_interfaces_status()
        except TeltonikaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TeltonikaError as err:
            raise UpdateFailed(str(err)) from err

        parts = await self._async_read_pages(
            [
                "interface_config",
                "wireless_config",
                "wireless_status",
                "wireless_devices",
                "modems",
                "gps",
                "usage",
                "dhcp",
                "wireguard",
                "sim_cards",
                "port_forwards",
                "traffic_rules",
                "failover",
                "failover_config",
                "data_limit",
                "sms",
                "data_usage_day",
                "data_usage_month",
                "firmware_updates",
                "firmware_progress",
                "firmware_device",
                *(f"vpn_{kind.key}_config" for kind in VPN_FAMILIES),
                *(f"vpn_{kind.key}_status" for kind in VPN_FAMILIES),
            ]
        )
        interface_config = parts["interface_config"] or []
        wireless_config = parts["wireless_config"] or []
        wireless_status = parts["wireless_status"] or []
        wireless_devices = parts["wireless_devices"] or []
        modems = parts["modems"] or []
        gps = self._hold_gps_glitches(parts["gps"])
        usage = parts["usage"]
        dhcp_leases = parts["dhcp"]
        wireguard_config = parts["wireguard"] or []
        sim_cards = parts["sim_cards"] or []
        port_forwards = parts["port_forwards"] or []
        traffic_rules = parts["traffic_rules"] or []
        failover = parts["failover"]
        failover_config = parts["failover_config"] or []
        data_limits = parts["data_limit"] or []
        multi_ap: list[dict[str, Any]] = []
        if any(item.get("mode") == "multi_ap" for item in wireless_config):
            multi_ap = (await self._async_read_pages(["multi_ap"]))["multi_ap"] or []

        updates = parts["firmware_updates"]
        if updates:
            self._firmware_updates_seen = updates
        elif self._firmware_busy():
            # The router may stop answering the update page while it downloads
            # or installs; the status keeps what it knew instead of going blank.
            updates = self._firmware_updates_seen
        installed = derive_installed_firmware(parts["firmware_device"]) or self.router.firmware
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
            usage=usage if isinstance(usage, dict) else None,
            dhcp_leases=dhcp_leases if isinstance(dhcp_leases, list) else None,
            wireguard_config=wireguard_config,
            sim_cards=sim_cards,
            failover=failover if isinstance(failover, dict) else None,
            failover_config=failover_config,
            data_limits=data_limits,
            port_forwards=port_forwards,
            traffic_rules=traffic_rules,
            data_plan_bytes=self._data_plan_bytes,
            sms=parts["sms"] if isinstance(parts["sms"], list) else None,
            data_usage_day=parts["data_usage_day"],
            data_usage_month=parts["data_usage_month"],
            firmware_updates=updates,
            firmware_installed=installed,
            firmware_progress=parts["firmware_progress"],
            vpn_config={
                kind.key: parts[f"vpn_{kind.key}_config"]
                if isinstance(parts[f"vpn_{kind.key}_config"], list)
                else None
                for kind in VPN_FAMILIES
            },
            vpn_status={kind.key: parts[f"vpn_{kind.key}_status"] for kind in VPN_FAMILIES},
        )
        data.portal_waiting = self.portal_waiting
        self._track_firmware(installed)
        self._remember_position(data)
        self._announce_new_sms(data)
        probe_internet = bool(self._probe_url) and data.uplink is not None
        internet, vpn = await asyncio.gather(
            self._async_probe_internet() if probe_internet else _nothing(),
            self._async_check_vpn() if self.vpn_host else _nothing(),
        )
        if probe_internet:
            data.internet = internet
        if self.vpn_host and vpn is not None:
            data.vpn_reachable, data.vpn_latency = vpn
        self._log_state(data)
        return data

    def _track_firmware(self, installed: str | None) -> None:
        """Follow the running firmware version and an installation in progress.

        A new version updates the stored router facts and the device entry,
        and ends the installation we started. An answer with the old version
        long after the start means the router did not restart.
        """
        if installed and installed != self.router.firmware:
            _LOGGER.info("The router runs a new firmware: %s", installed)
            self.router = replace(self.router, firmware=installed)
            registry = dr.async_get(self.hass)
            device = next(
                (
                    item
                    for item in dr.async_entries_for_config_entry(
                        registry, self.config_entry.entry_id
                    )
                    if (DOMAIN, self.router.unique_id) in item.identifiers
                ),
                None,
            )
            if device is not None:
                registry.async_update_device(device.id, sw_version=installed)
        if self.installing_since is None:
            return
        if installed and installed != self._install_from:
            self.installing_since = None
        elif time.monotonic() - self.installing_since > FIRMWARE_INSTALL_GRACE:
            _LOGGER.warning("The router answers with the old firmware: the installation failed")
            self.installing_since = None
            self.install_failed = True

    def _firmware_busy(self) -> bool:
        """Return whether a firmware download or installation is being followed."""
        return self.installing_since is not None or time.monotonic() < self._watch_download_until

    @property
    def firmware_state(self) -> str | None:
        """Return where the firmware update stands, None without update information."""
        if self.installing_since is not None:
            if time.monotonic() - self.installing_since > FIRMWARE_INSTALL_TIMEOUT:
                return "failed"
            return "installing"
        if self.install_failed:
            return "failed"
        firmware = self.data.firmware if self.data else None
        download = self.data.firmware_download if self.data else None
        if firmware is None:
            # Without update information the download progress still counts.
            if download is not None and self._download_running(download):
                return "downloading"
            return None
        if firmware.update_available is not True:
            # Also when the versions cannot be compared: say "up to date"
            # instead of guessing, like the update entity does.
            return "up_to_date"
        if (
            self.download_requested_at is not None
            and time.monotonic() - self.download_requested_at < FIRMWARE_DOWNLOAD_SETTLE
        ):
            return "downloading"
        if download is not None:
            if download.ready and not self.stale_download:
                return "ready"
            process = (download.process or "").lower()
            if "fail" in process or "error" in process:
                return "failed"
            watching = time.monotonic() < self._watch_download_until
            if self._download_running(download) or (watching and (download.percent or 0) < 100):
                return "downloading"
        return "update_available" if firmware.update_available else None

    @staticmethod
    def _download_running(download: FirmwareDownload) -> bool:
        process = (download.process or "").lower()
        return any(word in process for word in ("download", "progress", "running"))

    def _log_state(self, data: TeltonikaData) -> None:
        """Write what was found and decided to the debug log.

        The first update gets a report of what this router offers, which is the
        first thing to read when a feature does not work on another model. Every
        update gets one short summary line. No names, addresses or secrets.
        """
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return
        try:
            self._write_state_log(data)
        except Exception:  # noqa: BLE001
            # Writing the log must never break an update.
            _LOGGER.debug("Could not write the state summary", exc_info=True)

    def _write_state_log(self, data: TeltonikaData) -> None:
        uplink = data.uplink
        wifi = data.wifi_client
        online = [m for m in data.modems if m.get("id") and is_modem_online(m)]
        _LOGGER.debug(
            "Update: uplink=%s metric=%s wifi_first=%s wifi=%s internet=%s "
            "portal=%s modems_online=%d vpn_reachable=%s",
            uplink.kind if uplink else None,
            uplink.metric if uplink else None,
            data.wifi_first,
            f"{wifi.band} {wifi.signal} dBm" if wifi else None,
            data.internet,
            data.portal_state,
            len(online),
            data.vpn_reachable,
        )
        if self._reported:
            return
        self._reported = True
        _LOGGER.debug(
            "Router report: model=%s firmware=%s. Pages: %s",
            self.router.model,
            self.router.firmware,
            self.page_status(),
        )
        _LOGGER.debug(
            "Router report: modems=%d (online %d), sim settings=%d, radios=%d, "
            "wifi clients/multi AP=%d, access points=%d, gps=%s, "
            "wireguard tunnels=%d, usage=%s, dhcp=%s, failover interfaces=%d, "
            "data limits=%d, port forwards=%d, traffic rules=%d",
            len(data.modems),
            len(online),
            len(data.sim_cards),
            len(data.wireless_devices),
            len(data.stations),
            len(data.access_points),
            data.gps_available,
            len(data.vpn_tunnels),
            data.system_usage is not None,
            data.dhcp_leases is not None,
            len(data.failover),
            len(data.data_limits),
            len(data.port_forwards),
            len(data.traffic_rules),
        )
        for instance in data.vpn_instances:
            _LOGGER.debug(
                "VPN %s %s: enabled=%s connected=%s status text=%r",
                instance.family,
                instance.instance_id,
                instance.enabled,
                instance.connected,
                instance.status,
            )

    async def _async_read_pages(self, names: list[str]) -> dict[str, Any]:
        """Read router pages one after the other and return their answers.

        Status pages are read on every update. Configuration pages are read
        again only after the configuration interval or after an action of
        ours, which keeps the load on the router small. A missing page (an
        error answer) gives None and is asked again only after a long pause. A
        page that does not answer in time keeps its last known values and is
        asked again after a shorter pause, so one slow page neither takes all
        entities offline nor keeps a struggling router busy.
        """
        parts: dict[str, Any] = {}
        for name in names:
            method, kind, *args = PAGES[name]
            now = time.monotonic()
            ttl = {"status": 0.0, "medium": min(DHCP_INTERVAL, self._config_interval)}.get(
                kind, self._config_interval
            )
            if name == "firmware_progress" and now < self._watch_download_until:
                ttl = 0.0
            fetched = self._fetched_at.get(name)
            fresh = fetched is not None and now - fetched < ttl
            paused = now < self._slow_until.get(name, 0.0) or now < self._missing_until.get(
                name, 0.0
            )
            if (fresh or paused) and name in self._last_good:
                parts[name] = self._last_good[name]
                continue
            try:
                result = await getattr(self.client, method)(*args)
            except TeltonikaApiError as err:
                # Router without Wi-Fi, modem or GPS, or a user without the
                # right to read the page: the endpoint is missing.
                if name not in self._missing_until:
                    _LOGGER.debug(
                        "Page %s is not available on this router (HTTP %s: %s), "
                        "its entities are not created. It is asked again in %d s",
                        name,
                        err.status,
                        err,
                        MISSING_PAGE_PAUSE,
                    )
                self._page_notes[name] = f"missing (HTTP {err.status}: {err})"
                parts[name] = self._last_good[name] = None
                self._missing_until[name] = now + MISSING_PAGE_PAUSE
                self._slow_until.pop(name, None)
            except TeltonikaAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except TeltonikaConnectionError as err:
                self._page_notes[name] = f"slow ({err})"
                parts[name] = self._last_good.get(name)
                if name not in self._slow_until:
                    _LOGGER.warning(
                        "The router did not answer for %s in time, using the "
                        "last known values and asking again later",
                        name,
                    )
                _LOGGER.debug(
                    "Page %s: %s. Last known values are used for %d s",
                    name,
                    err,
                    SLOW_PAGE_PAUSE,
                )
                self._slow_until[name] = now + SLOW_PAGE_PAUSE
                # Remember that a value exists so the pause is honoured.
                self._last_good.setdefault(name, None)
            except Exception as err:  # noqa: BLE001
                raise UpdateFailed(f"Unexpected error: {err}") from err
            else:
                if name in self._slow_until:
                    _LOGGER.info("The router answers for %s again", name)
                    del self._slow_until[name]
                self._missing_until.pop(name, None)
                self._page_notes[name] = "ok"
                parts[name] = self._last_good[name] = result
                self._fetched_at[name] = now
        return parts

    def page_status(self) -> dict[str, str]:
        """Return for each router page whether it works, is missing or is slow."""
        return {name: self._page_notes.get(name, "not read yet") for name in PAGES}

    def page_shapes(self) -> dict[str, str]:
        """Return the structure (key names and types) of each page answer."""
        shapes = {
            name: shape_text(value)
            for name, value in self._last_good.items()
            if value is not None
        }
        shapes["interfaces"] = shape_text(self.data.interfaces)
        return shapes

    def _hold_gps_glitches(self, raw: Any) -> Any:
        """Keep the last reading while the receiver reports a few empty ones.

        The router now and then reports a reading with 0 satellites and an
        accuracy of 500 m between normal readings of 5 to 9 satellites. Such
        a single reading would make the sensors jump and could trigger zone
        automations. A few misses in a row are therefore ignored; if the
        receiver really has no fix any more, the empty reading shows up.
        """
        if not isinstance(raw, dict):
            return raw
        satellites = to_int(raw.get("satellites"))
        if satellites == 0:
            self._gps_misses += 1
            if self._last_fix is not None and self._gps_misses <= GPS_GLITCH_POLLS:
                return self._last_fix
            return raw
        if satellites:
            self._last_fix = raw
        self._gps_misses = 0
        return raw

    def _invalidate_config_pages(self) -> None:
        """Read the configuration pages again on the next update."""
        self._fetched_at.clear()
        self._missing_until.clear()

    async def async_request_refresh(self) -> None:
        """Refresh soon, after an action: configuration is read again too."""
        self._invalidate_config_pages()
        await super().async_request_refresh()

    async def async_refresh(self) -> None:
        """Refresh now: configuration is read again too."""
        self._invalidate_config_pages()
        await super().async_refresh()

    async def _async_check_vpn(self) -> tuple[bool, float | None]:
        """Connect to the host behind the tunnel; return (reachable, ms)."""
        started = time.perf_counter()
        try:
            async with asyncio.timeout(VPN_TIMEOUT):
                _, writer = await asyncio.open_connection(
                    self.vpn_host, self._vpn_port
                )
        except ConnectionRefusedError:
            # The host answered with a reset, so the tunnel carries traffic.
            return True, round((time.perf_counter() - started) * 1000, 1)
        except (OSError, TimeoutError):
            return False, None
        latency = round((time.perf_counter() - started) * 1000, 1)
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        return True, latency

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

    def _announce_new_sms(self, data: TeltonikaData) -> None:
        """Fire an event for every SMS that arrived since the last reading.

        The first reading only remembers what is in the inbox, so a restart of
        Home Assistant does not announce old messages again.
        """
        if data.sms is None:
            return
        keys = {message.key for message in data.sms}
        previous = self._sms_seen
        self._sms_seen = keys
        if previous is None:
            return
        for message in data.sms:
            if message.key in previous:
                continue
            self.hass.bus.async_fire(
                EVENT_SMS_RECEIVED,
                {
                    "router": self.router.unique_id,
                    "sender": message.sender,
                    "message": message.message,
                    "date": message.date,
                    "modem": message.modem_id,
                    "status": message.status,
                },
            )

    def modem_ids(self) -> list[str]:
        """Return the ids of all modems with a full status."""
        return [
            str(m.get("id"))
            for m in self.data.modems
            if m.get("id") and is_modem_online(m)
        ]

    async def async_send_sms(
        self, number: str, message: str, modem: str | None = None
    ) -> int | None:
        """Send an SMS and return how many SMS parts it used.

        Without a modem, the only modem with a full status is used. Neither the
        number nor the text is written to the log.
        """
        modem_id = modem
        if modem_id is None:
            modems = self.modem_ids()
            if len(modems) != 1:
                raise HomeAssistantError(
                    "Choose the modem to send with: "
                    + (", ".join(modems) if modems else "no modem is online")
                )
            modem_id = modems[0]
        _LOGGER.debug("Action: send an SMS through modem %s", modem_id)
        async with translate_errors():
            return await self.client.async_send_sms(modem_id, number, message)

    async def async_send_composed_sms(self) -> None:
        """Send the SMS typed into the text entities and report the result.

        The text is cleared after a successful send so it is not sent twice;
        the number stays for the next message.
        """
        number = clean_phone_number(self.sms_number)
        if number is None:
            self._report_sms("Not sent: enter a phone number")
            raise HomeAssistantError(PHONE_NUMBER_HINT)
        if not self.sms_text.strip():
            self._report_sms("Not sent: enter a text")
            raise HomeAssistantError("Enter the text of the SMS first")
        try:
            used = await self.async_send_sms(number, self.sms_text)
        except HomeAssistantError as err:
            self._report_sms(f"Not sent: {err}")
            raise
        self.sms_text = ""
        parts = f" ({used} parts)" if used and used > 1 else ""
        self._report_sms(f"Sent{parts}")

    def _report_sms(self, text: str) -> None:
        """Remember the result of the last SMS for the sensor."""
        self.last_sms = text
        self.async_update_listeners()

    async def async_download_firmware(self) -> None:
        """Let the router download the firmware it found. Nothing is installed."""
        firmware = self.data.firmware
        if firmware is None or firmware.update_available is False:
            raise HomeAssistantError("The router has found no newer firmware")
        _LOGGER.debug("Action: download firmware %s (%s)", firmware.latest, firmware.channel)
        self.install_failed = False
        async with translate_errors():
            await self.client.async_firmware_download(firmware.channel)
        # The progress page still shows the last result for a moment: until it
        # has caught up, the old "succeeded" must not count as this download.
        self.download_requested_at = time.monotonic()
        self.stale_download = False
        self._watch_download_until = self.download_requested_at + FIRMWARE_WATCH_SECONDS
        await self.async_request_refresh()

    async def async_install_firmware(self) -> None:
        """Install the downloaded firmware. The router restarts.

        The router drops the connection while it restarts, which is the
        expected end of this request, so a lost connection is not an error.
        """
        firmware = self.data.firmware
        if firmware is None or firmware.update_available is False:
            raise HomeAssistantError("The router has found no newer firmware")
        if self.firmware_state != "ready":
            raise HomeAssistantError("Download the firmware first and wait until it is complete")
        if self.installing_since is not None:
            raise HomeAssistantError("The firmware installation is already running")
        _LOGGER.warning(
            "Installing firmware %s: the router restarts and is offline for a few minutes",
            firmware.latest,
        )
        self._install_from = firmware.installed
        self.install_failed = False
        self.installing_since = time.monotonic()
        self.async_update_listeners()
        try:
            async with translate_errors():
                try:
                    await self.client.async_firmware_upgrade(keep_settings=True)
                except TeltonikaConnectionError:
                    _LOGGER.debug("Connection lost while the router starts the firmware upgrade")
        except HomeAssistantError as err:
            self.installing_since = None
            # The router says it has no file: its "succeeded" was an old result.
            if "not found" in str(err).lower():
                self.stale_download = True
            self.async_update_listeners()
            raise
        finally:
            await self.async_request_refresh()

    async def async_restart_mobile(self, modem_id: str) -> None:
        """Re-establish the mobile data connection."""
        _LOGGER.debug("Action: restart the mobile connection of a modem")
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
        _LOGGER.debug("Action: reboot the router")
        async with translate_errors():
            await self.client.async_reboot()

    async def async_set_access_point(self, config_id: str, enabled: bool) -> None:
        """Switch one of the router's own access points on or off."""
        _LOGGER.debug("Action: access point %s -> enabled=%s", config_id, enabled)
        async with translate_errors():
            await self.client.async_set_wireless_enabled(config_id, enabled)
        await asyncio.sleep(AP_REFRESH_DELAY)
        await self.async_request_refresh()

    async def async_set_vpn_tunnel(self, tunnel_id: str, enabled: bool) -> None:
        """Enable or disable a WireGuard tunnel."""
        _LOGGER.debug("Action: WireGuard %s -> enabled=%s", tunnel_id, enabled)
        self._require_switchable_tunnel(tunnel_id)
        async with translate_errors():
            await self.client.async_set_wireguard_enabled(tunnel_id, enabled)
        await asyncio.sleep(VPN_REFRESH_DELAY)
        await self.async_request_refresh()

    async def async_reconnect_vpn(self, tunnel_id: str) -> None:
        """Restart a WireGuard tunnel by switching its instance off and on."""
        _LOGGER.debug("Action: restart WireGuard %s (off, wait, on)", tunnel_id)
        tunnel = self._require_switchable_tunnel(tunnel_id)
        if tunnel.enabled is False:
            raise HomeAssistantError(
                f"The tunnel {tunnel_id} is switched off. Switch it on instead."
            )
        async with translate_errors():
            await self.client.async_set_wireguard_enabled(tunnel_id, False)
        await asyncio.sleep(VPN_RECONNECT_DELAY)
        try:
            async with translate_errors():
                await self.client.async_set_wireguard_enabled(tunnel_id, True)
        except HomeAssistantError as err:
            raise HomeAssistantError(
                f"The tunnel {tunnel_id} was switched off but could not be "
                f"switched on again: {err}. Switch it on manually."
            ) from err
        await asyncio.sleep(VPN_REFRESH_DELAY)
        await self.async_request_refresh()

    def _require_switchable_tunnel(self, tunnel_id: str) -> VpnTunnel:
        for tunnel in self.data.vpn_tunnels:
            if tunnel.tunnel_id == tunnel_id:
                if tunnel.enabled is None:
                    raise HomeAssistantError(
                        "The router user may not read or change the WireGuard "
                        "configuration."
                    )
                return tunnel
        raise HomeAssistantError(f"Tunnel {tunnel_id} not found")

    async def async_set_vpn_instance(self, family: str, instance_id: str, enabled: bool) -> None:
        """Switch an instance of Tailscale, OpenVPN, IPsec or SSTP on or off."""
        _LOGGER.debug("Action: %s %s -> enabled=%s", family, instance_id, enabled)
        self._require_vpn_instance(family, instance_id)
        async with translate_errors():
            await self.client.async_set_vpn_enabled(family, instance_id, enabled)
        await asyncio.sleep(VPN_REFRESH_DELAY)
        await self.async_request_refresh()

    async def async_reconnect_vpn_instance(self, family: str, instance_id: str) -> None:
        """Restart an instance by switching it off and on again."""
        _LOGGER.debug("Action: restart %s %s (off, wait, on)", family, instance_id)
        instance = self._require_vpn_instance(family, instance_id)
        if instance.enabled is False:
            raise HomeAssistantError(
                f"{instance.label} is switched off. Switch it on instead."
            )
        async with translate_errors():
            await self.client.async_set_vpn_enabled(family, instance_id, False)
        await asyncio.sleep(VPN_RECONNECT_DELAY)
        try:
            async with translate_errors():
                await self.client.async_set_vpn_enabled(family, instance_id, True)
        except HomeAssistantError as err:
            raise HomeAssistantError(
                f"{instance.label} was switched off but could not be switched "
                f"on again: {err}. Switch it on manually."
            ) from err
        await asyncio.sleep(VPN_REFRESH_DELAY)
        await self.async_request_refresh()

    def _require_vpn_instance(self, family: str, instance_id: str) -> VpnInstance:
        for instance in self.data.vpn_instances:
            if instance.family == family and instance.instance_id == instance_id:
                if instance.enabled is None:
                    raise HomeAssistantError(
                        f"The router user may not change the {instance.label} configuration."
                    )
                return instance
        raise HomeAssistantError(f"{family} {instance_id} not found")

    async def async_set_roaming(self, card_id: str, allowed: bool) -> None:
        """Allow or deny data roaming of one SIM and check that it took effect."""
        _LOGGER.debug("Action: data roaming of SIM settings %s -> allowed=%s", card_id, allowed)
        card = next((c for c in self.data.sim_cards if c.card_id == card_id), None)
        if card is None:
            raise HomeAssistantError(f"SIM settings {card_id} not found")
        async with translate_errors():
            await self.client.async_set_sim_roaming(card_id, allowed)
        await asyncio.sleep(ROAMING_REFRESH_DELAY)
        await self.async_refresh()
        current = next((c for c in self.data.sim_cards if c.card_id == card_id), None)
        if current is None or current.roaming_allowed is not allowed:
            raise HomeAssistantError(
                "The router did not apply the roaming setting. Check it in "
                "Network, Mobile, General, SIM configuration."
            )

    async def async_set_port_forward(self, rule_id: str, enabled: bool) -> None:
        """Turn a port forwarding rule on or off and check that it took effect."""
        _LOGGER.debug("Action: port forward %s -> enabled=%s", rule_id, enabled)
        if not any(rule.rule_id == rule_id for rule in self.data.port_forwards):
            raise HomeAssistantError(f"Port forward {rule_id} not found")
        async with translate_errors():
            await self.client.async_set_port_forward_enabled(rule_id, enabled)
        await asyncio.sleep(PORT_FORWARD_REFRESH_DELAY)
        await self.async_refresh()
        current = next(
            (rule for rule in self.data.port_forwards if rule.rule_id == rule_id), None
        )
        if current is None or current.enabled is not enabled:
            raise HomeAssistantError(
                "The router did not apply the port forward setting. Check it in "
                "Network, Firewall, Port forwards."
            )

    async def async_set_traffic_rule(self, rule_id: str, enabled: bool) -> None:
        """Turn a traffic rule on or off and check that it took effect."""
        _LOGGER.debug("Action: traffic rule %s -> enabled=%s", rule_id, enabled)
        if not any(rule.rule_id == rule_id for rule in self.data.traffic_rules):
            raise HomeAssistantError(f"Traffic rule {rule_id} not found")
        async with translate_errors():
            await self.client.async_set_traffic_rule_enabled(rule_id, enabled)
        await asyncio.sleep(PORT_FORWARD_REFRESH_DELAY)
        await self.async_refresh()
        current = next(
            (rule for rule in self.data.traffic_rules if rule.rule_id == rule_id), None
        )
        if current is None or current.enabled is not enabled:
            raise HomeAssistantError(
                "The router did not apply the traffic rule setting. Check it in "
                "Network, Firewall, Traffic rules."
            )

    async def async_switch_sim(self, modem_id: str, target_sim: int) -> None:
        """Switch a dual SIM modem to the requested slot."""
        _LOGGER.debug("Action: switch SIM to slot %s", target_sim)
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
        _LOGGER.debug("Action: priority wifi_first=%s verify=%s", wifi_first, verify)
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
        _LOGGER.debug("Action: Wi-Fi scan, radio=%s", radio or "all")
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
        if self.scanning:
            return
        # The scan takes a few seconds; say so at once instead of staying silent.
        self.scanning = True
        self._report("Scanning for networks ...")
        try:
            found = await self.async_scan_wifi(None)
        except HomeAssistantError as err:
            self._report(f"Scan failed: {err}")
            raise
        finally:
            self.scanning = False
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
                # The failover page is read at most every two minutes; read it
                # now, because the Wi-Fi only counts once the router sees it online.
                self._fetched_at.pop("failover", None)
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
