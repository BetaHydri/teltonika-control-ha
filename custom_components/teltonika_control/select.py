"""Selects for Teltonika routers."""

from __future__ import annotations

from functools import partial

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PRIORITY_MOBILE_FIRST, PRIORITY_WIFI_FIRST
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity, TeltonikaModemEntity, async_add_discovered

PARALLEL_UPDATES = 1

SIM_OPTIONS = ["sim_1", "sim_2"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the selects."""
    coordinator = entry.runtime_data
    async_add_entities([TeltonikaPrioritySelect(coordinator)])
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (f"{m.get('id')}_sim", partial(TeltonikaSimSelect, c, str(m.get("id"))))
            for m in c.data.modems
            if m.get("id") and int(m.get("sim_count") or 0) == 2
        ),
    )


class TeltonikaPrioritySelect(TeltonikaEntity, SelectEntity):
    """Chooses between Wi-Fi first and mobile first."""

    _attr_translation_key = "priority"
    _attr_options = [PRIORITY_WIFI_FIRST, PRIORITY_MOBILE_FIRST]

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "priority")

    @property
    def available(self) -> bool:
        """Return False if the router has no saved Wi-Fi network."""
        return super().available and self.coordinator.data.wifi_first is not None

    @property
    def current_option(self) -> str | None:
        """Return the current priority."""
        wifi_first = self.coordinator.data.wifi_first
        if wifi_first is None:
            return None
        return PRIORITY_WIFI_FIRST if wifi_first else PRIORITY_MOBILE_FIRST

    async def async_select_option(self, option: str) -> None:
        """Change the priority."""
        await self.coordinator.async_set_wifi_priority(option == PRIORITY_WIFI_FIRST)


class TeltonikaSimSelect(TeltonikaModemEntity, SelectEntity):
    """Switches a dual SIM modem between its two slots."""

    _attr_translation_key = "sim"
    _attr_options = SIM_OPTIONS

    def __init__(self, coordinator: TeltonikaCoordinator, modem_id: str) -> None:
        super().__init__(coordinator, modem_id, "sim")

    @property
    def current_option(self) -> str | None:
        """Return the active SIM slot."""
        modem = self.modem
        if modem is None:
            return None
        slot = f"sim_{modem.get('active_sim')}"
        return slot if slot in SIM_OPTIONS else None

    async def async_select_option(self, option: str) -> None:
        """Switch the SIM; the mobile connection drops for about a minute."""
        await self.coordinator.async_switch_sim(
            self._modem_id, SIM_OPTIONS.index(option) + 1
        )
