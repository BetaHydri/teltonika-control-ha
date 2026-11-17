"""GPS position of the router as a device tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
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
    """Add the tracker once the router reports that it has GPS."""
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("gps", lambda: TeltonikaGpsTracker(c)),) if c.data.gps_available else ()
        ),
    )


class TeltonikaGpsTracker(TeltonikaEntity, TrackerEntity):
    """The position of the router, for example the camper or boat it sits in."""

    _attr_translation_key = "gps"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "gps")

    @property
    def source_type(self) -> SourceType:
        """Return GPS as the source of the position."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return the latitude: live, else the last known one."""
        position = self.coordinator.data.gps_position
        return position.latitude if position else None

    @property
    def longitude(self) -> float | None:
        """Return the longitude: live, else the last known one."""
        position = self.coordinator.data.gps_position
        return position.longitude if position else None

    @property
    def location_accuracy(self) -> float:
        """Return the accuracy in meters."""
        position = self.coordinator.data.gps_position
        return position.accuracy if position and position.accuracy is not None else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Say whether the position is live or the last one with a fix."""
        data = self.coordinator.data
        attributes: dict[str, Any] = {"fix": bool(data.gps_fix)}
        if data.gps_last_fix is not None:
            attributes["last_fix"] = data.gps_last_fix.isoformat()
        return attributes
