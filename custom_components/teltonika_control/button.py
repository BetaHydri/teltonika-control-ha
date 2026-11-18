"""Buttons for Teltonika routers."""

from __future__ import annotations

from functools import partial

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import (
    TeltonikaEntity,
    TeltonikaModemEntity,
    TeltonikaTunnelEntity,
    TeltonikaVpnEntity,
    async_add_discovered,
)
from .models import VpnInstance

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
                f"vpnx_{instance.family}_{instance.instance_id}",
                lambda i=instance: TeltonikaReconnectVpnInstanceButton(c, i),
            )
            for instance in c.data.vpn_instances
            if instance.enabled is not None
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (key, partial(button_class, c))
            for key, button_class in WIFI_MANAGEMENT_BUTTONS
            if c.data.wireless_devices
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"vpn_{tunnel.tunnel_id}_reconnect",
                lambda t=tunnel.tunnel_id: TeltonikaReconnectVpnButton(c, t),
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
                f"{modem_id}_restart_mobile",
                lambda m=modem_id: TeltonikaRestartMobileButton(c, m),
            )
            for modem_id in c.modem_ids()
        ),
    )


class TeltonikaReconnectVpnButton(TeltonikaTunnelEntity, ButtonEntity):
    """Restarts a WireGuard tunnel by switching it off and on."""

    _attr_translation_key = "reconnect_vpn"

    def __init__(self, coordinator: TeltonikaCoordinator, tunnel_id: str) -> None:
        super().__init__(coordinator, tunnel_id, "reconnect")

    async def async_press(self) -> None:
        """Restart the tunnel."""
        await self.coordinator.async_reconnect_vpn(self._tunnel_id)


class TeltonikaReconnectVpnInstanceButton(TeltonikaVpnEntity, ButtonEntity):
    """Restarts a Tailscale, OpenVPN, IPsec or SSTP instance by switching it off and on."""

    _attr_translation_key = "reconnect_vpn_instance"

    def __init__(self, coordinator: TeltonikaCoordinator, instance: VpnInstance) -> None:
        super().__init__(coordinator, instance, "reconnect")

    async def async_press(self) -> None:
        """Restart the instance."""
        await self.coordinator.async_reconnect_vpn_instance(self._family, self._instance_id)


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


class TeltonikaScanWifiButton(TeltonikaEntity, ButtonEntity):
    """Scans for Wi-Fi networks and fills the list of found networks."""

    _attr_translation_key = "scan_wifi"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "scan_wifi")

    async def async_press(self) -> None:
        """Scan with all radios."""
        await self.coordinator.async_scan_networks()


class TeltonikaAddNetworkButton(TeltonikaEntity, ButtonEntity):
    """Saves the selected found network with the entered password."""

    _attr_translation_key = "add_network"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "add_network")

    async def async_press(self) -> None:
        """Save the selected network."""
        await self.coordinator.async_add_selected_network()


class TeltonikaRemoveNetworkButton(TeltonikaEntity, ButtonEntity):
    """Removes the selected saved network."""

    _attr_translation_key = "remove_network"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "remove_network")

    async def async_press(self) -> None:
        """Remove the selected network."""
        await self.coordinator.async_remove_selected_network()


WIFI_MANAGEMENT_BUTTONS = (
    ("scan_wifi", TeltonikaScanWifiButton),
    ("add_network", TeltonikaAddNetworkButton),
    ("remove_network", TeltonikaRemoveNetworkButton),
)
