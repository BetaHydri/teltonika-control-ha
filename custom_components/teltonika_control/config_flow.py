"""Config flow for Teltonika Control."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import (
    TeltonikaAuthError,
    TeltonikaClient,
    TeltonikaConnectionError,
    TeltonikaError,
    parse_host,
)
from .const import (
    CONF_CONFIG_INTERVAL,
    CONF_DATA_PLAN,
    CONF_PRESENCE_DELAY,
    CONF_PROBE_URL,
    CONF_SCAN_INTERVAL,
    CONF_TRACKED_DEVICES,
    CONF_VPN_HOST,
    CONF_VPN_PORT,
    DEFAULT_CONFIG_INTERVAL,
    DEFAULT_PRESENCE_DELAY,
    DEFAULT_PROBE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DEFAULT_VPN_PORT,
    DOMAIN,
    MAX_CONFIG_INTERVAL,
    MAX_PRESENCE_DELAY,
    MAX_SCAN_INTERVAL,
    MIN_CONFIG_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .models import RouterInfo, normalize_mac

_LOGGER = logging.getLogger(__name__)

_BRACKETED = re.compile(r"^\[(?P<host>[^\]]+)\](?::(?P<port>\d+))?$")
_HOSTNAME = re.compile(r"^[A-Za-z0-9._:-]+$")


def parse_vpn_target(value: str) -> tuple[str, int | None] | None:
    """Split a DNS name, IPv4 or IPv6 address with an optional port.

    Accepts ``name``, ``name:443``, ``fd00::1``, ``[fd00::1]`` and
    ``[fd00::1]:443``. Returns None for anything that is not a plain host.
    """
    text = value.strip()
    if not text:
        return None
    port: int | None = None
    bracketed = _BRACKETED.match(text)
    if bracketed:
        text = bracketed.group("host")
        port = int(bracketed.group("port")) if bracketed.group("port") else None
    elif text.count(":") == 1:
        text, _, port_text = text.partition(":")
        if not port_text.isdigit():
            return None
        port = int(port_text)
    if not text or not _HOSTNAME.match(text):
        return None
    if port is not None and not 1 <= port <= 65535:
        return None
    return text, port


def build_client(hass: HomeAssistant, data: Mapping[str, Any]) -> TeltonikaClient:
    """Create a client from config entry data."""
    host, use_ssl = parse_host(data[CONF_HOST])
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, False))
    return TeltonikaClient(
        session,
        host,
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        use_ssl=use_ssl,
    )


async def async_validate(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> RouterInfo:
    """Log in and read the router identity."""
    client = build_client(hass, data)
    await client.async_login()
    status = await client.async_device_status()
    return RouterInfo.from_device_status(client.host, status)


class TeltonikaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup of one router."""

    VERSION = 1

    def __init__(self) -> None:
        """Remember the address of a router found on the network."""
        self._discovered_host: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> TeltonikaOptionsFlow:
        """Return the options flow."""
        return TeltonikaOptionsFlow()

    def _entry_for_mac(self, mac: str) -> ConfigEntry | None:
        """Return the router entry whose device has this MAC address."""
        registry = dr.async_get(self.hass)
        wanted = (CONNECTION_NETWORK_MAC, mac)
        for entry in self._async_current_entries():
            for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
                if wanted in device.connections:
                    return entry
        return None

    async def _async_address_is_gone(self, entry: ConfigEntry, host: str) -> bool:
        """Tell whether a known router moved: the old address is silent, the new one answers.

        An address that still answers is never replaced, because the router
        can be seen on more than one address (LAN, WAN, VPN).
        """
        if parse_host(entry.data[CONF_HOST])[0] == host:
            return False
        try:
            await async_validate(self.hass, entry.data)
        except TeltonikaConnectionError:
            pass
        except TeltonikaError:
            return False
        else:
            return False
        try:
            info = await async_validate(self.hass, {**entry.data, CONF_HOST: host})
        except TeltonikaError:
            return False
        return info.unique_id == entry.unique_id

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        """A Teltonika router asked for an address on the network."""
        mac = format_mac(discovery_info.macaddress)
        host = discovery_info.ip
        entry = self._entry_for_mac(mac)
        if entry is not None:
            await self.async_set_unique_id(entry.unique_id)
            if await self._async_address_is_gone(entry, host):
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()
        self._discovered_host = host
        self.context["title_placeholders"] = {
            "name": discovery_info.hostname or "Teltonika",
            "host": host,
        }
        return await self.async_step_dhcp_confirm()

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the login of the router that was found."""
        host = self._discovered_host or ""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_HOST: host,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_VERIFY_SSL: False,
            }
            info, data, errors = await self._async_try_both(data)
            if info is not None:
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: data[CONF_HOST]})
                return self.async_create_entry(title=info.name, data=data)

        defaults = user_input or {}
        return self.async_show_form(
            step_id="dhcp_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"host": host},
            errors=errors,
        )

    async def _async_try(
        self, data: Mapping[str, Any]
    ) -> tuple[RouterInfo | None, dict[str, str]]:
        try:
            return await async_validate(self.hass, data), {}
        except TeltonikaAuthError:
            return None, {"base": "invalid_auth"}
        except TeltonikaConnectionError:
            return None, {"base": "cannot_connect"}
        except TeltonikaError:
            _LOGGER.exception("Unexpected router answer")
            return None, {"base": "unknown"}

    async def _async_try_both(
        self, data: Mapping[str, Any]
    ) -> tuple[RouterInfo | None, dict[str, Any], dict[str, str]]:
        """Connect, and fall back to plain HTTP when HTTPS cannot be reached.

        Only an address without ``http://`` or ``https://`` is tried twice. The
        data that worked is returned, so that the entry keeps the right scheme.
        """
        info, errors = await self._async_try(data)
        host = str(data[CONF_HOST]).strip()
        if (
            info is not None
            or errors != {"base": "cannot_connect"}
            or host.lower().startswith(("http://", "https://"))
        ):
            return info, dict(data), errors
        plain = {**data, CONF_HOST: f"http://{host}"}
        plain_info, plain_errors = await self._async_try(plain)
        if plain_info is not None or plain_errors != {"base": "cannot_connect"}:
            return plain_info, plain, plain_errors
        return None, dict(data), errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host and credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info, data, errors = await self._async_try_both(user_input)
            if info is not None:
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: data[CONF_HOST]}
                )
                return self.async_create_entry(title=info.name, data=data)

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "192.168.1.1")): str,
                    vol.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(
                        CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, False)
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication after the router rejected the login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            info, errors = await self._async_try(data)
            if info is not None:
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host, user or password of an existing router."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            info, data, errors = await self._async_try_both(user_input)
            if info is not None:
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=data)

        current = user_input or entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current[CONF_HOST]): str,
                    vol.Required(CONF_USERNAME, default=current[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(
                        CONF_VERIFY_SSL, default=current.get(CONF_VERIFY_SSL, False)
                    ): bool,
                }
            ),
            errors=errors,
        )


class TeltonikaOptionsFlow(OptionsFlow):
    """Polling interval, internet probe and VPN check."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # An emptied field is missing from user_input: store "" to disable it.
            vpn_host = ""
            vpn_port = user_input.get(CONF_VPN_PORT, DEFAULT_VPN_PORT)
            raw_vpn = user_input.get(CONF_VPN_HOST, "").strip()
            if raw_vpn:
                target = parse_vpn_target(raw_vpn)
                if target is None:
                    errors[CONF_VPN_HOST] = "invalid_vpn_host"
                else:
                    vpn_host = target[0]
                    # A port typed behind the host wins over the port field.
                    vpn_port = target[1] or vpn_port
            if not errors:
                tracked: list[str] = []
                for raw_mac in user_input.get(CONF_TRACKED_DEVICES) or []:
                    mac = normalize_mac(raw_mac)
                    if mac is None:
                        errors[CONF_TRACKED_DEVICES] = "invalid_mac"
                        break
                    if mac not in tracked:
                        tracked.append(mac)
            if not errors:
                return self.async_create_entry(
                    data={
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                        CONF_CONFIG_INTERVAL: user_input.get(
                            CONF_CONFIG_INTERVAL, DEFAULT_CONFIG_INTERVAL
                        ),
                        CONF_PROBE_URL: user_input.get(CONF_PROBE_URL, "").strip(),
                        CONF_VPN_HOST: vpn_host,
                        CONF_VPN_PORT: vpn_port,
                        CONF_DATA_PLAN: user_input.get(CONF_DATA_PLAN, 0),
                        CONF_TRACKED_DEVICES: tracked,
                        CONF_PRESENCE_DELAY: user_input.get(
                            CONF_PRESENCE_DELAY, DEFAULT_PRESENCE_DELAY
                        ),
                    }
                )

        options = self.config_entry.options
        suggested = user_input or options
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Optional(
                        CONF_CONFIG_INTERVAL,
                        default=options.get(
                            CONF_CONFIG_INTERVAL, DEFAULT_CONFIG_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_CONFIG_INTERVAL, max=MAX_CONFIG_INTERVAL),
                    ),
                    vol.Optional(
                        CONF_PROBE_URL,
                        description={
                            "suggested_value": suggested.get(
                                CONF_PROBE_URL,
                                "" if user_input is not None else DEFAULT_PROBE_URL,
                            )
                        },
                    ): str,
                    vol.Optional(
                        CONF_VPN_HOST,
                        description={
                            "suggested_value": suggested.get(CONF_VPN_HOST, "")
                        },
                    ): str,
                    vol.Optional(
                        CONF_VPN_PORT,
                        default=options.get(CONF_VPN_PORT, DEFAULT_VPN_PORT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Optional(
                        CONF_DATA_PLAN,
                        description={
                            "suggested_value": suggested.get(CONF_DATA_PLAN) or None
                        },
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100000)),
                    vol.Optional(
                        CONF_TRACKED_DEVICES,
                        description={
                            "suggested_value": suggested.get(CONF_TRACKED_DEVICES) or []
                        },
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=self._device_options(
                                suggested.get(CONF_TRACKED_DEVICES) or []
                            ),
                            multiple=True,
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_PRESENCE_DELAY,
                        default=options.get(CONF_PRESENCE_DELAY, DEFAULT_PRESENCE_DELAY),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=MAX_PRESENCE_DELAY)
                    ),
                }
            ),
        )

    def _device_options(self, chosen: list[str]) -> list[SelectOptionDict]:
        """Return the devices the router knows, those on the Wi-Fi first."""
        runtime = getattr(self.config_entry, "runtime_data", None)
        clients = runtime.data.clients if runtime is not None else []
        options: list[SelectOptionDict] = []
        listed: set[str] = set()
        for client in sorted(
            clients,
            key=lambda c: (
                not c.connected,
                c.hostname is None,
                (c.hostname or "").lower(),
                c.mac,
            ),
        ):
            marker = "● " if client.connected else ""
            options.append(
                SelectOptionDict(
                    value=client.mac,
                    label=f"{marker}{client.hostname or '?'} ({client.mac})",
                )
            )
            listed.add(client.mac)
        for raw_mac in chosen:
            mac = normalize_mac(raw_mac)
            if mac is not None and mac not in listed:
                options.append(SelectOptionDict(value=mac, label=mac))
                listed.add(mac)
        return options
