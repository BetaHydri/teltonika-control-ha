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

from .const import PORTAL_LOGIN_REQUIRED, UPLINK_ETHERNET, UPLINK_MOBILE, UPLINK_WIFI
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import (
    TeltonikaEntity,
    TeltonikaModemEntity,
    TeltonikaTunnelEntity,
    async_add_discovered,
)
from .models import DataLimit, FailoverInterface, TeltonikaData, modem_is_roaming

PARALLEL_UPDATES = 0

FAILOVER_KINDS = {UPLINK_MOBILE, UPLINK_WIFI, UPLINK_ETHERNET}

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
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"{modem_id}_roaming",
                lambda m=modem_id: TeltonikaModemRoaming(c, m),
            )
            for modem_id in c.modem_ids()
        ),
    )

    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"failover_{interface.interface_id}_online",
                lambda i=interface.interface_id: TeltonikaFailoverOnline(c, i),
            )
            for interface in c.data.failover
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"failover_kind_{kind}",
                lambda k=kind: TeltonikaFailoverKindOnline(c, k),
            )
            for kind in sorted({i.kind for i in c.data.failover} & FAILOVER_KINDS)
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("gps_signal", lambda: TeltonikaGpsSignal(c)),)
            if c.data.gps_available
            else ()
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"data_limit_{limit.interface_id}_reached",
                lambda i=limit.interface_id: TeltonikaDataLimitReached(c, i),
            )
            for limit in c.data.data_limits
        ),
    )


class TeltonikaFailoverKindOnline(TeltonikaEntity, BinarySensorEntity):
    """On while any uplink of one kind (mobile, Wi-Fi, Ethernet) is online.

    The entity has the same name on every router, so a dashboard or an
    automation does not need the interface names of the router.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: TeltonikaCoordinator, kind: str) -> None:
        super().__init__(coordinator, f"failover_kind_{kind}")
        self._kind = kind
        self._attr_translation_key = f"failover_{kind}_online"

    @property
    def _interfaces(self) -> list[FailoverInterface]:
        return [i for i in self.coordinator.data.failover if i.kind == self._kind]

    @property
    def available(self) -> bool:
        """Return False if no interface of this kind is in the failover."""
        return super().available and bool(self._interfaces)

    @property
    def is_on(self) -> bool | None:
        """Return whether any interface of this kind is online."""
        states = [i.online for i in self._interfaces if i.online is not None]
        return any(states) if states else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the interfaces of this kind that are online."""
        return {
            "online_interfaces": [i.label for i in self._interfaces if i.online],
            "interfaces": [i.label for i in self._interfaces],
        }


class TeltonikaFailoverOnline(TeltonikaEntity, BinarySensorEntity):
    """Whether the failover check says this uplink is online."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "failover_online"

    def __init__(self, coordinator: TeltonikaCoordinator, interface_id: str) -> None:
        super().__init__(coordinator, f"failover_{interface_id}_online")
        self._interface_id = interface_id
        interface = self.interface
        self._attr_translation_placeholders = {
            "name": interface.label if interface else interface_id
        }

    @property
    def interface(self) -> FailoverInterface | None:
        """Return the current failover state of this interface."""
        for interface in self.coordinator.data.failover:
            if interface.interface_id == self._interface_id:
                return interface
        return None

    @property
    def available(self) -> bool:
        """Return False if the interface left the failover configuration."""
        return super().available and self.interface is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the uplink is online."""
        interface = self.interface
        return interface.online if interface else None


class TeltonikaGpsSignal(TeltonikaEntity, BinarySensorEntity):
    """Whether the GPS receiver has a fix, so that the position is current."""

    _attr_translation_key = "gps_signal"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "gps_signal")

    @property
    def is_on(self) -> bool | None:
        """Return whether the receiver has a fix."""
        return self.coordinator.data.gps_fix

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the satellites in use and when the last fix was."""
        data = self.coordinator.data
        attributes: dict[str, Any] = {"satellites": data.gps_satellites}
        if data.gps_last_fix is not None:
            attributes["last_fix"] = data.gps_last_fix.isoformat()
        return attributes


class TeltonikaDataLimitReached(TeltonikaEntity, BinarySensorEntity):
    """On while the data limit of a mobile interface is used up."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "data_limit_reached"

    def __init__(self, coordinator: TeltonikaCoordinator, interface_id: str) -> None:
        super().__init__(coordinator, f"data_limit_{interface_id}_reached")
        self._interface_id = interface_id
        limit = self.limit
        self._attr_translation_placeholders = {
            "name": limit.label if limit else interface_id
        }

    @property
    def limit(self) -> DataLimit | None:
        """Return the current data limit of this interface."""
        for limit in self.coordinator.data.data_limits:
            if limit.interface_id == self._interface_id:
                return limit
        return None

    @property
    def available(self) -> bool:
        """Return False if the limit was switched off on the router."""
        return super().available and self.limit is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the limit is used up."""
        limit = self.limit
        return limit.reached if limit else None


class TeltonikaModemRoaming(TeltonikaModemEntity, BinarySensorEntity):
    """On while the modem is registered in a foreign network (roaming)."""

    _attr_translation_key = "roaming"

    def __init__(self, coordinator: TeltonikaCoordinator, modem_id: str) -> None:
        super().__init__(coordinator, modem_id, "roaming")

    @property
    def is_on(self) -> bool | None:
        """Return the roaming state."""
        modem: dict[str, Any] | None = self.modem
        return modem_is_roaming(modem) if modem is not None else None


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
