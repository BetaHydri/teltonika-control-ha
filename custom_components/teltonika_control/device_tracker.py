"""Device trackers: the router's GPS position and who is on its Wi-Fi."""

from __future__ import annotations

from functools import partial
from typing import Any

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.components.device_tracker import (
    ScannerEntity,
    SourceType,
    TrackerEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity, async_add_discovered
from .models import ClientDevice

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the trackers of the chosen devices and the GPS position."""
    coordinator = entry.runtime_data
    _remove_untracked(hass, entry, coordinator)
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (f"presence_{mac}", partial(TeltonikaPresenceTracker, c, mac))
            for mac in c.tracked_macs
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("gps", lambda: TeltonikaGpsTracker(c)),) if c.data.gps_available else ()
        ),
    )


@callback
def _remove_untracked(
    hass: HomeAssistant, entry: TeltonikaConfigEntry, coordinator: TeltonikaCoordinator
) -> None:
    """Remove the trackers of devices that were taken out of the options."""
    prefix = f"{coordinator.router.unique_id}_presence_"
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity.domain == DEVICE_TRACKER_DOMAIN
            and entity.unique_id.startswith(prefix)
            and entity.unique_id[len(prefix) :] not in coordinator.tracked_macs
        ):
            registry.async_remove(entity.entity_id)


class TeltonikaPresenceTracker(TeltonikaEntity, ScannerEntity):
    """A device that is home while it is connected to the router's Wi-Fi."""

    _attr_translation_key = "presence"
    _attr_entity_category = None
    # Change on nearly every update; no use in the history.
    _unrecorded_attributes = frozenset({"signal", "inactive_seconds"})

    def __init__(self, coordinator: TeltonikaCoordinator, mac: str) -> None:
        super().__init__(coordinator, f"presence_{mac}")
        self._mac = mac
        self._attr_mac_address = mac
        client = self._client
        self._attr_translation_placeholders = {
            "device": (client.hostname if client and client.hostname else None) or mac
        }

    @property
    def _client(self) -> ClientDevice | None:
        return next((c for c in self.coordinator.data.clients if c.mac == self._mac), None)

    @property
    def unique_id(self) -> str | None:
        """Return an ID that belongs to this router and device."""
        return self._attr_unique_id

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Chosen devices are enabled, also when no device entry knows the MAC."""
        return True

    @property
    def available(self) -> bool:
        """Return False while the router never told who is on the Wi-Fi."""
        return super().available and self.coordinator.data.presence_ready

    @property
    def is_connected(self) -> bool:
        """Return whether the device is on the Wi-Fi or just left it."""
        return self._mac in self.coordinator.data.present

    @property
    def ip_address(self) -> str | None:
        """Return the address of the device from the router's lease list."""
        client = self._client
        return client.ip if client else None

    @property
    def hostname(self) -> str | None:
        """Return the name of the device from the router's lease list."""
        client = self._client
        return client.hostname if client else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return what the router says about the device while it is on the Wi-Fi.

        `signal` is in dBm; `inactive_seconds` is how long the router has not
        heard from the device (the value the option "Seconds of silence until
        away" compares with).
        """
        device = self.coordinator.data.associated.get(self._mac)
        if device is None:
            return {}
        attributes: dict[str, Any] = {"wifi_network": device.ssid, "wifi_band": device.band}
        if device.signal is not None:
            attributes["signal"] = round(device.signal)
        if device.inactive is not None:
            attributes["inactive_seconds"] = round(device.inactive)
        return attributes


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
