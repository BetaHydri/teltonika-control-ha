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
                ("firmware_download", lambda: TeltonikaDownloadFirmwareButton(c)),
                ("firmware_install", lambda: TeltonikaInstallFirmwareButton(c)),
            )
            if c.data.firmware is not None and c.data.firmware_download is not None
            else ()
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("sms_send", lambda: TeltonikaSendSmsButton(c)),)
            if c.data.sms is not None
            else ()
        ),
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


class TeltonikaDownloadFirmwareButton(TeltonikaEntity, ButtonEntity):
    """Lets the router download the firmware it found. Nothing is installed."""

    _attr_translation_key = "download_firmware"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "firmware_download")

    @property
    def available(self) -> bool:
        """Return True while the router has found a newer firmware."""
        firmware = self.coordinator.data.firmware
        return (
            super().available and firmware is not None and firmware.update_available is not False
        )

    async def async_press(self) -> None:
        """Start the download."""
        await self.coordinator.async_download_firmware()


class TeltonikaInstallFirmwareButton(TeltonikaEntity, ButtonEntity):
    """Installs the downloaded firmware. The router restarts and is offline for minutes.

    Disabled by default: enable it on purpose and put a confirmation in front
    of it in your dashboard.
    """

    _attr_translation_key = "install_firmware"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "firmware_install")

    @property
    def available(self) -> bool:
        """Return True once a complete firmware file waits on the router."""
        data = self.coordinator.data
        return (
            super().available
            and data.firmware is not None
            and data.firmware.update_available is not False
            and data.firmware_download is not None
            and data.firmware_download.ready
        )

    async def async_press(self) -> None:
        """Install the firmware."""
        await self.coordinator.async_install_firmware()


class TeltonikaSendSmsButton(TeltonikaEntity, ButtonEntity):
    """Sends the SMS typed into the number and text fields. Costs what an SMS costs."""

    _attr_translation_key = "send_sms"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "sms_send")

    async def async_press(self) -> None:
        """Send the SMS."""
        await self.coordinator.async_send_composed_sms()


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
