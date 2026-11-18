"""Switches for access points, WireGuard tunnels, data roaming and port forwards."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import (
    TeltonikaEntity,
    TeltonikaModemEntity,
    TeltonikaTunnelEntity,
    TeltonikaVpnEntity,
    async_add_discovered,
)
from .models import (
    TRAFFIC_GROUP_SYSTEM,
    AccessPoint,
    PortForward,
    SimCard,
    TrafficRule,
    VpnInstance,
)

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
                f"vpnx_{instance.family}_{instance.instance_id}",
                lambda i=instance: TeltonikaVpnInstanceSwitch(c, i),
            )
            for instance in c.data.vpn_instances
            if instance.enabled is not None
        ),
    )
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
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"vpn_{tunnel.tunnel_id}",
                lambda t=tunnel.tunnel_id: TeltonikaTunnelSwitch(c, t),
            )
            for tunnel in c.data.vpn_tunnels
            if tunnel.enabled is not None
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"{card.modem_id}_roaming_sim{card.slot}",
                lambda m=card.modem_id, s=card.slot: TeltonikaRoamingSwitch(c, m, s),
            )
            for card in c.data.sim_cards
            if card.modem_id in c.modem_ids()
            and card.slot is not None
            and card.roaming_allowed is not None
        ),
    )

    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"port_forward_{rule.rule_id}",
                lambda r=rule.rule_id: TeltonikaPortForwardSwitch(c, r),
            )
            for rule in c.data.port_forwards
        ),
    )

    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"traffic_rule_{rule.rule_id}",
                lambda r=rule.rule_id: TeltonikaTrafficRuleSwitch(c, r),
            )
            for rule in c.data.traffic_rules
        ),
    )


class TeltonikaTrafficRuleSwitch(TeltonikaEntity, SwitchEntity):
    """Turns a traffic rule of the router firewall on or off.

    Only the on/off flag of the rule is written. The router's own rules
    ("Allow-...") are created disabled; enable the ones you want in the entity
    settings. A rule that is on can let the internet reach the router or your
    network, and switching off the rule that carries your own remote access
    locks you out.
    """

    _attr_translation_key = "traffic_rule"

    def __init__(self, coordinator: TeltonikaCoordinator, rule_id: str) -> None:
        super().__init__(coordinator, f"traffic_rule_{rule_id}")
        self._rule_id = rule_id
        rule = self.rule
        self._attr_translation_placeholders = {"name": rule.name if rule else rule_id}
        self._attr_entity_registry_enabled_default = (
            rule is None or rule.group != TRAFFIC_GROUP_SYSTEM
        )

    @property
    def rule(self) -> TrafficRule | None:
        """Return the current settings of this rule."""
        for rule in self.coordinator.data.traffic_rules:
            if rule.rule_id == self._rule_id:
                return rule
        return None

    @property
    def available(self) -> bool:
        """Return False if the rule was removed from the router."""
        return super().available and self.rule is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the rule is on."""
        rule = self.rule
        return rule.enabled if rule else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return what the rule matches and does."""
        rule = self.rule
        if rule is None:
            return None
        return {
            "kind": "traffic_rule",
            "group": rule.group,
            "source_zone": rule.source,
            "destination_zone": rule.destination,
            "protocol": rule.protocol,
            "ports": rule.ports,
            "action": rule.action,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the rule on."""
        await self.coordinator.async_set_traffic_rule(self._rule_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the rule off."""
        await self.coordinator.async_set_traffic_rule(self._rule_id, False)


class TeltonikaPortForwardSwitch(TeltonikaEntity, SwitchEntity):
    """Turns a port forwarding rule of the router firewall on or off.

    Only the on/off flag of the rule is written. A rule that is on lets
    traffic from the internet reach a device in your network.
    """

    _attr_translation_key = "port_forward"

    def __init__(self, coordinator: TeltonikaCoordinator, rule_id: str) -> None:
        super().__init__(coordinator, f"port_forward_{rule_id}")
        self._rule_id = rule_id
        rule = self.rule
        self._attr_translation_placeholders = {"name": rule.name if rule else rule_id}

    @property
    def rule(self) -> PortForward | None:
        """Return the current settings of this rule."""
        for rule in self.coordinator.data.port_forwards:
            if rule.rule_id == self._rule_id:
                return rule
        return None

    @property
    def available(self) -> bool:
        """Return False if the rule was removed from the router."""
        return super().available and self.rule is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the rule is on."""
        rule = self.rule
        return rule.enabled if rule else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the ports and protocol of the rule."""
        rule = self.rule
        if rule is None:
            return None
        return {
            "kind": "port_forward",
            "protocol": rule.protocol,
            "external_port": rule.external_port,
            "internal_port": rule.internal_port,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the rule on."""
        await self.coordinator.async_set_port_forward(self._rule_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the rule off."""
        await self.coordinator.async_set_port_forward(self._rule_id, False)


class TeltonikaRoamingSwitch(TeltonikaModemEntity, SwitchEntity):
    """Allows or denies data roaming of one SIM (the router's setting).

    On means roaming is allowed, which is the opposite of the router's "Deny
    data roaming". Only this one field is written.
    """

    _attr_translation_key = "data_roaming"

    def __init__(
        self, coordinator: TeltonikaCoordinator, modem_id: str, slot: int
    ) -> None:
        super().__init__(coordinator, modem_id, f"roaming_sim{slot}")
        self._slot = slot
        self._attr_translation_placeholders = {"slot": str(slot)}

    @property
    def card(self) -> SimCard | None:
        """Return the current settings of this SIM."""
        for card in self.coordinator.data.sim_cards:
            if card.modem_id == self._modem_id and card.slot == self._slot:
                return card
        return None

    @property
    def available(self) -> bool:
        """Return False if the SIM settings are gone from the router."""
        return super().available and self.card is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether data roaming is allowed."""
        card = self.card
        return card.roaming_allowed if card else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Allow data roaming."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deny data roaming."""
        await self._async_set(False)

    async def _async_set(self, allowed: bool) -> None:
        card = self.card
        if card is None:
            raise HomeAssistantError("SIM settings not found")
        await self.coordinator.async_set_roaming(card.card_id, allowed)


class TeltonikaTunnelSwitch(TeltonikaTunnelEntity, SwitchEntity):
    """Turns a WireGuard instance on or off (its configuration flag)."""

    _attr_translation_key = "tunnel"

    def __init__(self, coordinator: TeltonikaCoordinator, tunnel_id: str) -> None:
        super().__init__(coordinator, tunnel_id, "switch")

    @property
    def is_on(self) -> bool | None:
        """Return whether the instance is enabled."""
        tunnel = self.tunnel
        return tunnel.enabled if tunnel else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the tunnel."""
        await self.coordinator.async_set_vpn_tunnel(self._tunnel_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the tunnel."""
        await self.coordinator.async_set_vpn_tunnel(self._tunnel_id, False)


class TeltonikaVpnInstanceSwitch(TeltonikaVpnEntity, SwitchEntity):
    """Turns a Tailscale, OpenVPN, IPsec or SSTP instance on or off (connect, disconnect)."""

    _attr_translation_key = "vpn_instance"

    def __init__(self, coordinator: TeltonikaCoordinator, instance: VpnInstance) -> None:
        super().__init__(coordinator, instance, "switch")

    @property
    def is_on(self) -> bool | None:
        """Return whether the instance is enabled."""
        instance = self.instance
        return instance.enabled if instance else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the instance."""
        await self.coordinator.async_set_vpn_instance(self._family, self._instance_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the instance."""
        await self.coordinator.async_set_vpn_instance(self._family, self._instance_id, False)


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
