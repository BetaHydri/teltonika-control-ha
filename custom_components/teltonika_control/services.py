"""Services of the Teltonika Control integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_PORTAL_MINUTES, DOMAIN
from .coordinator import TeltonikaCoordinator

ATTR_DEVICE_ID = "device_id"

SERVICE_PORTAL_MODE = "portal_mode"
SERVICE_SET_PRIORITY = "set_priority"
SERVICE_SCAN_WIFI = "scan_wifi"
SERVICE_JOIN_WIFI = "join_wifi"
SERVICE_FORGET_WIFI = "forget_wifi"

BASE_SCHEMA = {vol.Required(ATTR_DEVICE_ID): cv.string}


def _coordinator(hass: HomeAssistant, device_id: str) -> TeltonikaCoordinator:
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is not None
                and entry.domain == DOMAIN
                and entry.state is ConfigEntryState.LOADED
            ):
                return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="router_not_found"
    )


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register all services."""

    async def portal_mode(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_start_portal_mode(call.data["minutes"])

    async def set_priority(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        success = await coordinator.async_set_wifi_priority(
            call.data["wifi_first"], verify=call.data["verify"]
        )
        return {"success": success}

    async def scan_wifi(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        networks = await coordinator.async_scan_wifi(call.data.get("radio"))
        return {"networks": networks}

    async def join_wifi(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_join_wifi(
            radio=call.data["radio"],
            ssid=call.data["ssid"],
            bssid=call.data.get("bssid"),
            password=call.data.get("password"),
        )

    async def forget_wifi(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_forget_wifi(
            call.data.get("station_id"), call.data.get("ssid")
        )

    schemas: dict[str, Any] = {
        SERVICE_PORTAL_MODE: vol.Schema(
            {
                **BASE_SCHEMA,
                vol.Optional("minutes", default=DEFAULT_PORTAL_MINUTES): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=30)
                ),
            }
        ),
        SERVICE_SET_PRIORITY: vol.Schema(
            {
                **BASE_SCHEMA,
                vol.Required("wifi_first"): cv.boolean,
                vol.Optional("verify", default=True): cv.boolean,
            }
        ),
        SERVICE_SCAN_WIFI: vol.Schema(
            {**BASE_SCHEMA, vol.Optional("radio"): cv.string}
        ),
        SERVICE_JOIN_WIFI: vol.Schema(
            {
                **BASE_SCHEMA,
                vol.Required("radio"): cv.string,
                vol.Required("ssid"): cv.string,
                vol.Optional("bssid"): cv.string,
                vol.Optional("password"): cv.string,
            }
        ),
        SERVICE_FORGET_WIFI: vol.Schema(
            vol.All(
                {
                    **BASE_SCHEMA,
                    vol.Exclusive("station_id", "target"): cv.string,
                    vol.Exclusive("ssid", "target"): cv.string,
                },
                cv.has_at_least_one_key("station_id", "ssid"),
            )
        ),
    }

    hass.services.async_register(
        DOMAIN, SERVICE_PORTAL_MODE, portal_mode, schemas[SERVICE_PORTAL_MODE]
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PRIORITY,
        set_priority,
        schemas[SERVICE_SET_PRIORITY],
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_WIFI,
        scan_wifi,
        schemas[SERVICE_SCAN_WIFI],
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_JOIN_WIFI, join_wifi, schemas[SERVICE_JOIN_WIFI]
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FORGET_WIFI, forget_wifi, schemas[SERVICE_FORGET_WIFI]
    )
