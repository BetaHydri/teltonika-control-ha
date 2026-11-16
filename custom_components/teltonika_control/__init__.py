"""Teltonika Control: native Home Assistant control for RUTC and RUTX routers."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .api import TeltonikaAuthError, TeltonikaError
from .config_flow import build_client
from .const import DOMAIN
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .models import RouterInfo
from .services import async_register_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration services once."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Set up one router."""
    client = build_client(hass, entry.data)
    try:
        await client.async_login()
        router = RouterInfo.from_device_status(
            client.host, await client.async_device_status()
        )
    except TeltonikaAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except TeltonikaError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = TeltonikaCoordinator(hass, entry, client, router)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **coordinator.router_device_info,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def _async_reload_on_options(
    hass: HomeAssistant, entry: TeltonikaConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Unload a router."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
