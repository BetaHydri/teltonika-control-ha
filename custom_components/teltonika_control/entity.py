"""Base entities and helpers shared by all platforms."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .models import is_modem_online


def _via_router(coordinator: TeltonikaCoordinator) -> dict[str, Any]:
    """Link a child device to the router in the way the running HA expects.

    Newer Home Assistant versions identify the parent by its device id and
    deprecate the identifier tuple; older versions only know the tuple.
    """
    router_id = coordinator.router.unique_id
    lookup = getattr(dr, "async_get_device_id_by_identifier", None)
    if lookup is not None:
        try:
            return {
                "via_device_id": lookup(
                    coordinator.hass,
                    (DOMAIN, router_id),
                    config_entry_id=coordinator.config_entry.entry_id,
                )
            }
        except ValueError:
            return {}
    return {"via_device": (DOMAIN, router_id)}


class TeltonikaEntity(CoordinatorEntity[TeltonikaCoordinator]):
    """An entity that belongs to the router device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TeltonikaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.router.unique_id}_{key}"
        self._attr_device_info = coordinator.router_device_info


class TeltonikaModemEntity(TeltonikaEntity):
    """An entity that belongs to one modem (child device of the router)."""

    def __init__(
        self, coordinator: TeltonikaCoordinator, modem_id: str, key: str
    ) -> None:
        super().__init__(coordinator, f"{modem_id}_{key}")
        self._modem_id = modem_id
        modem = self.modem or {}
        router_id = coordinator.router.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{router_id}_{modem_id}")},
            name=str(modem.get("name") or modem.get("model") or f"Modem {modem_id}"),
            manufacturer=str(modem.get("manufacturer") or "Teltonika"),
            model=modem.get("model"),
            **_via_router(coordinator),
        )

    @property
    def modem(self) -> dict[str, Any] | None:
        """Return the current status of this modem."""
        return self.coordinator.data.modem(self._modem_id)

    @property
    def available(self) -> bool:
        """Return False while the modem reports no full status."""
        modem = self.modem
        return super().available and modem is not None and is_modem_online(modem)


@callback
def async_add_discovered(
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discover: Callable[[TeltonikaCoordinator], Iterable[tuple[str, Callable[[], Entity]]]],
) -> None:
    """Add entities now and whenever the router reports new modems or radios."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new: list[Entity] = []
        for key, factory in discover(coordinator):
            if key not in known:
                known.add(key)
                new.append(factory())
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))
