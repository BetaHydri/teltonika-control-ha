"""Buttons for Teltonika routers."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity, TeltonikaModemEntity, async_add_discovered

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        [TeltonikaRebootButton(coordinator), TeltonikaReconnectWifiButton(coordinator)]
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"{modem_id}_restart_mobile",
                lambda m=modem_id: TeltonikaRestartMobileButton(c, m),
            )
            for modem_id in c.modem_ids()
        ),
    )


class TeltonikaRebootButton(TeltonikaEntity, ButtonEntity):
    """Reboots the router. Add a confirmation in your dashboard."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_translation_key = "reboot"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "reboot")

    async def async_press(self) -> None:
        """Reboot the router."""
        await self.coordinator.async_reboot()


class TeltonikaReconnectWifiButton(TeltonikaEntity, ButtonEntity):
    """Reconnects the saved Wi-Fi client networks."""

    _attr_translation_key = "reconnect_wifi"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "reconnect_wifi")

    async def async_press(self) -> None:
        """Reconnect Wi-Fi."""
        await self.coordinator.async_reconnect_wifi()


class TeltonikaRestartMobileButton(TeltonikaModemEntity, ButtonEntity):
    """Re-establishes the mobile data connection."""

    _attr_translation_key = "restart_mobile"

    def __init__(self, coordinator: TeltonikaCoordinator, modem_id: str) -> None:
        super().__init__(coordinator, modem_id, "restart_mobile")

    async def async_press(self) -> None:
        """Restart the mobile connection."""
        await self.coordinator.async_restart_mobile(self._modem_id)
