"""The Wi-Fi password and SMS fields."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity, async_add_discovered

PARALLEL_UPDATES = 0

MASK = "********"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Wi-Fi password field on routers with Wi-Fi and the SMS fields on routers with SMS."""
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("wifi_password", lambda: TeltonikaWifiPasswordText(c)),)
            if c.data.wireless_devices
            else ()
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                ("sms_number", lambda: TeltonikaSmsNumberText(c)),
                ("sms_text", lambda: TeltonikaSmsTextText(c)),
            )
            if c.data.sms is not None
            else ()
        ),
    )


class TeltonikaSmsNumberText(TeltonikaEntity, TextEntity):
    """The phone number of the next SMS, kept in memory until Home Assistant restarts."""

    _attr_translation_key = "sms_number"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 30

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "sms_number")

    @property
    def native_value(self) -> str:
        """Return the number as typed."""
        return self.coordinator.sms_number

    async def async_set_value(self, value: str) -> None:
        """Remember the number for the next SMS."""
        self.coordinator.sms_number = value
        self.coordinator.async_update_listeners()


class TeltonikaSmsTextText(TeltonikaEntity, TextEntity):
    """The text of the next SMS; it is cleared after a successful send.

    Home Assistant limits a state to 255 characters. Longer texts go through
    the ``send_sms`` service.
    """

    _attr_translation_key = "sms_text"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 255

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "sms_text")

    @property
    def native_value(self) -> str:
        """Return the text as typed."""
        return self.coordinator.sms_text

    async def async_set_value(self, value: str) -> None:
        """Remember the text for the next SMS."""
        self.coordinator.sms_text = value
        self.coordinator.async_update_listeners()


class TeltonikaWifiPasswordText(TeltonikaEntity, TextEntity):
    """The password for the next network that is added.

    The password is kept in memory only. The state always shows a mask, so the
    password never ends up in the history or in a backup.
    """

    _attr_translation_key = "wifi_password"
    _attr_mode = TextMode.PASSWORD
    _attr_native_min = 0
    _attr_native_max = 63

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "wifi_password")

    @property
    def native_value(self) -> str:
        """Return a mask while a password is set, an empty text otherwise."""
        return MASK if self.coordinator.wifi_password else ""

    async def async_set_value(self, value: str) -> None:
        """Remember the password for the next Add network."""
        if value == MASK and self.coordinator.wifi_password:
            return
        self.coordinator.wifi_password = value
        self.coordinator.async_update_listeners()
