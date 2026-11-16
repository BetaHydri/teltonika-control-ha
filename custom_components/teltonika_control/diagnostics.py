"""Diagnostics for Teltonika Control."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_VPN_HOST
from .coordinator import TeltonikaConfigEntry

TO_REDACT = {
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VPN_HOST,
    "serial",
    "mac",
    "ssid",
    "bssid",
    "key",
    "password",
    "imei",
    "imsi",
    "iccid",
    "cellid",
    "ipaddrs",
    "ip",
    "gwaddr",
    "macaddr",
    "serial_number",
    "operator",
    "provider",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TeltonikaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with personal data removed."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return async_redact_data(
        {
            "entry": dict(entry.data),
            "options": dict(entry.options),
            "router": asdict(coordinator.router),
            "uplink": asdict(data.uplink) if data.uplink else None,
            "wifi_client": asdict(data.wifi_client) if data.wifi_client else None,
            "wifi_first": data.wifi_first,
            "internet": data.internet,
            "vpn_reachable": data.vpn_reachable,
            "vpn_latency": data.vpn_latency,
            "router_pages": coordinator.page_status(),
            "answer_structure": coordinator.page_shapes(),
            "portal_state": data.portal_state,
            "access_points": [asdict(point) for point in data.access_points],
            "stations": [asdict(station) for station in data.stations],
            "modems": data.modems,
            "wireless_devices": data.wireless_devices,
        },
        TO_REDACT,
    )
