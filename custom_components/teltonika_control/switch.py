"""Switches for the router's own access points."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity, async_add_discovered
from .models import AccessPoint

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one switch per access point."""
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                ap.config_id,
                lambda cid=ap.config_id: TeltonikaAccessPointSwitch(c, cid),
            )
            for ap in c.data.access_points
        ),
    )


class TeltonikaAccessPointSwitch(TeltonikaEntity, SwitchEntity):
    """Turns an access point of the router on or off.

    The state comes from the router configuration, not from the last
    command, so changes made in the router web interface show up as well.
    """

    _attr_translation_key = "access_point"

    def __init__(self, coordinator: TeltonikaCoordinator, config_id: str) -> None:
        super().__init__(coordinator, f"ap_{config_id}")
        self._config_id = config_id
        point = self.access_point
        self._attr_translation_placeholders = {
            "name": point.label if point else config_id
        }

    @property
    def access_point(self) -> AccessPoint | None:
        """Return the current state of this access point."""
        for point in self.coordinator.data.access_points:
            if point.config_id == self._config_id:
                return point
        return None

    @property
    def available(self) -> bool:
        """Return False if the access point was removed from the router."""
        return super().available and self.access_point is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the access point is enabled."""
        point = self.access_point
        return point.enabled if point else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the access point."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the access point."""
        await self._async_set(False)

    async def _async_set(self, enabled: bool) -> None:
        if self.access_point is None:
            raise HomeAssistantError("Access point not found")
        await self.coordinator.async_set_access_point(self._config_id, enabled)
