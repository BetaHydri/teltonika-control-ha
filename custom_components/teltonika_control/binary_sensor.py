"""Binary sensors for Teltonika routers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PORTAL_LOGIN_REQUIRED, UPLINK_WIFI
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import (
    TeltonikaEntity,
    TeltonikaModemEntity,
    TeltonikaTunnelEntity,
    async_add_discovered,
)
from .models import TeltonikaData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RouterBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a binary sensor of the router."""

    value_fn: Callable[[TeltonikaData], bool | None]


ROUTER_BINARY_SENSORS: tuple[RouterBinarySensorDescription, ...] = (
    RouterBinarySensorDescription(
        key="wifi_connected",
        translation_key="wifi_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.wifi_client is not None
        or (d.uplink is not None and d.uplink.kind == UPLINK_WIFI),
    ),
    RouterBinarySensorDescription(
        key="internet",
        translation_key="internet",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.internet,
    ),
    RouterBinarySensorDescription(
        key="login_required",
        translation_key="login_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.portal_state == PORTAL_LOGIN_REQUIRED,
    ),
)

VPN_BINARY_SENSOR = RouterBinarySensorDescription(
    key="vpn_reachable",
    translation_key="vpn_reachable",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    value_fn=lambda d: d.vpn_reachable,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    descriptions = list(ROUTER_BINARY_SENSORS)
    if coordinator.vpn_host:
        descriptions.append(VPN_BINARY_SENSOR)
    async_add_entities(
        TeltonikaRouterBinarySensor(coordinator, description)
        for description in descriptions
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"vpn_{tunnel.tunnel_id}_up",
                lambda t=tunnel.tunnel_id: TeltonikaTunnelUp(c, t),
            )
            for tunnel in c.data.vpn_tunnels
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"{modem_id}_mobile_connected",
                lambda m=modem_id: TeltonikaMobileConnected(c, m),
            )
            for modem_id in c.modem_ids()
        ),
    )


class TeltonikaTunnelUp(TeltonikaTunnelEntity, BinarySensorEntity):
    """Whether the tunnel interface is up on the router.

    This says the interface exists and has an address, not that the other
    end answers. Use the VPN check for that.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "tunnel_up"

    def __init__(self, coordinator: TeltonikaCoordinator, tunnel_id: str) -> None:
        super().__init__(coordinator, tunnel_id, "up")

    @property
    def is_on(self) -> bool | None:
        """Return the interface state."""
        tunnel = self.tunnel
        return tunnel.up if tunnel else None


class TeltonikaRouterBinarySensor(TeltonikaEntity, BinarySensorEntity):
    """A binary sensor of the router."""

    entity_description: RouterBinarySensorDescription

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        description: RouterBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)


class TeltonikaMobileConnected(TeltonikaModemEntity, BinarySensorEntity):
    """Whether the modem has a data connection."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "mobile_connected"

    def __init__(self, coordinator: TeltonikaCoordinator, modem_id: str) -> None:
        super().__init__(coordinator, modem_id, "mobile_connected")

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        modem: dict[str, Any] | None = self.modem
        if modem is None:
            return None
        return str(modem.get("data_conn_state", "")).lower() == "connected"
