"""Firmware of the router as an update entity (read only)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity, async_add_discovered

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the entity once the router reports firmware update information."""
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("firmware", lambda: TeltonikaFirmwareUpdate(c)),)
            if c.data.firmware is not None
            else ()
        ),
    )


class TeltonikaFirmwareUpdate(TeltonikaEntity, UpdateEntity):
    """Says whether the router found a newer firmware.

    It only informs. The router downloads and installs firmware on its own, in
    its web interface.
    """

    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "firmware")

    @property
    def installed_version(self) -> str | None:
        """Return the firmware the router runs."""
        info = self.coordinator.data.firmware
        return info.installed if info else None

    @property
    def latest_version(self) -> str | None:
        """Return the newest stable firmware, or the installed one when unsure."""
        info = self.coordinator.data.firmware
        if info is None:
            return None
        return info.latest if info.update_available else info.installed

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Compare with the router's own version scheme, not a generic one."""
        info = self.coordinator.data.firmware
        return bool(info and info.update_available)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the newest release when it differs from the stable one."""
        info = self.coordinator.data.firmware
        if info is None or not info.newest or info.newest == info.latest:
            return {}
        return {"newest_release": info.newest}
