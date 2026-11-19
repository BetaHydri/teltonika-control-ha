"""Sensors for Teltonika routers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import BANDS, FIRMWARE_STATES, PORTAL_STATES, SMS_INBOX_SIZE, UPLINK_KINDS
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import (
    TeltonikaEntity,
    TeltonikaModemEntity,
    TeltonikaTunnelEntity,
    async_add_discovered,
)
from .models import (
    DataLimit,
    DataUsage,
    FailoverInterface,
    TeltonikaData,
    VpnTunnel,
    guard_counter,
    modem_registration,
    modem_temperature,
    newest_sms,
    to_float,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RouterSensorDescription(SensorEntityDescription):
    """Describes a sensor of the router."""

    value_fn: Callable[[TeltonikaData], StateType]
    attrs_fn: Callable[[TeltonikaData], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class ModemSensorDescription(SensorEntityDescription):
    """Describes a sensor of a modem."""

    value_fn: Callable[[dict[str, Any]], StateType]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _rounded(value: float | None, digits: int = 0) -> float | None:
    """Round so that GPS noise does not create a new state on every poll."""
    return None if value is None else round(value, digits)


ROUTER_TIME_SENSOR = RouterSensorDescription(
    key="router_time",
    translation_key="router_time",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    value_fn=lambda d: d.router_time,
)

VPN_LATENCY_SENSOR = RouterSensorDescription(
    key="vpn_latency",
    translation_key="vpn_latency",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.MILLISECONDS,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda d: d.vpn_latency,
)

OPEN_PORT_FORWARDS_SENSOR = RouterSensorDescription(
    key="open_port_forwards",
    translation_key="open_port_forwards",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: sum(1 for rule in d.port_forwards if rule.enabled),
    attrs_fn=lambda d: {
        "rules": [rule.name for rule in d.port_forwards if rule.enabled]
    },
)

OPEN_INTERNET_RULES_SENSOR = RouterSensorDescription(
    key="open_internet_rules",
    translation_key="open_internet_rules",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: sum(1 for rule in d.traffic_rules if rule.opens_internet),
    attrs_fn=lambda d: {
        "rules": [rule.name for rule in d.traffic_rules if rule.opens_internet]
    },
)


def _usage(data: TeltonikaData, name: str) -> StateType:
    return getattr(data.system_usage, name, None) if data.system_usage else None


def _dhcp_attributes(data: TeltonikaData) -> dict[str, Any]:
    return {
        "devices": [
            {
                "hostname": str(lease.get("hostname") or ""),
                "ip": str(lease.get("ipaddr") or ""),
                "interface": str(lease.get("interface") or ""),
            }
            for lease in data.dhcp_leases or []
        ]
    }


SYSTEM_SENSORS: tuple[RouterSensorDescription, ...] = (
    RouterSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _usage(d, "uptime"),
    ),
    RouterSensorDescription(
        key="cpu_load",
        translation_key="cpu_load",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _usage(d, "cpu_load"),
    ),
    RouterSensorDescription(
        key="ram_usage",
        translation_key="ram_usage",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _usage(d, "ram_usage"),
    ),
    RouterSensorDescription(
        key="flash_usage",
        translation_key="flash_usage",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _usage(d, "flash_usage"),
    ),
)

DHCP_CLIENTS_SENSOR = RouterSensorDescription(
    key="dhcp_clients",
    translation_key="dhcp_clients",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: len(d.dhcp_leases) if d.dhcp_leases is not None else None,
    attrs_fn=_dhcp_attributes,
)

GPS_SENSORS: tuple[RouterSensorDescription, ...] = (
    RouterSensorDescription(
        key="gps_speed",
        translation_key="gps_speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _rounded(d.gps.speed) if d.gps else None,
    ),
    RouterSensorDescription(
        key="gps_altitude",
        translation_key="gps_altitude",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _rounded(d.gps.altitude) if d.gps else None,
    ),
    RouterSensorDescription(
        key="gps_satellites",
        translation_key="gps_satellites",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.gps_satellites,
    ),
    RouterSensorDescription(
        key="gps_accuracy",
        translation_key="gps_accuracy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _rounded(d.gps.accuracy, 1) if d.gps else None,
    ),
    RouterSensorDescription(
        key="gps_heading",
        translation_key="gps_heading",
        native_unit_of_measurement=DEGREE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _rounded(d.gps.heading) if d.gps else None,
    ),
    RouterSensorDescription(
        key="gps_fix",
        translation_key="gps_fix",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.gps.fix_status if d.gps else None,
    ),
)


ROUTER_SENSORS: tuple[RouterSensorDescription, ...] = (
    RouterSensorDescription(
        key="uplink",
        translation_key="uplink",
        device_class=SensorDeviceClass.ENUM,
        options=UPLINK_KINDS,
        value_fn=lambda d: d.uplink.kind if d.uplink else None,
        attrs_fn=lambda d: (
            {
                "interface": d.uplink.name,
                "metric": d.uplink.metric,
                "wifi_ssid": d.wifi_client.ssid if d.wifi_client else None,
                "failover_skipped": d.uplink.skipped,
            }
            if d.uplink
            else {}
        ),
    ),
    RouterSensorDescription(
        key="uplink_ip",
        translation_key="uplink_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.uplink.ip if d.uplink else None,
    ),
    RouterSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        value_fn=lambda d: d.wifi_client.ssid if d.wifi_client else None,
        attrs_fn=lambda d: (
            {"channel": d.wifi_client.channel} if d.wifi_client else {}
        ),
    ),
    RouterSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.wifi_client.signal if d.wifi_client else None,
    ),
    RouterSensorDescription(
        key="wifi_bitrate",
        translation_key="wifi_bitrate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.wifi_client.bitrate if d.wifi_client else None,
    ),
    RouterSensorDescription(
        key="wifi_band",
        translation_key="wifi_band",
        device_class=SensorDeviceClass.ENUM,
        options=BANDS,
        value_fn=lambda d: d.wifi_client.band if d.wifi_client else None,
    ),
    RouterSensorDescription(
        key="portal_state",
        translation_key="portal_state",
        device_class=SensorDeviceClass.ENUM,
        options=PORTAL_STATES,
        value_fn=lambda d: d.portal_state,
    ),
)

MODEM_SENSORS: tuple[ModemSensorDescription, ...] = (
    ModemSensorDescription(
        key="operator",
        translation_key="operator",
        value_fn=lambda m: _text(m.get("operator") or m.get("provider")),
    ),
    ModemSensorDescription(
        key="registration",
        translation_key="registration",
        value_fn=modem_registration,
    ),
    ModemSensorDescription(
        key="connection_type",
        translation_key="connection_type",
        value_fn=lambda m: _text(m.get("conntype")),
    ),
    ModemSensorDescription(
        key="band",
        translation_key="band",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: _text(m.get("band")),
    ),
    ModemSensorDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda m: to_float(m.get("rssi")),
    ),
    ModemSensorDescription(
        key="rsrp",
        translation_key="rsrp",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m: to_float(m.get("rsrp")),
    ),
    ModemSensorDescription(
        key="rsrq",
        translation_key="rsrq",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m: to_float(m.get("rsrq")),
    ),
    ModemSensorDescription(
        key="sinr",
        translation_key="sinr",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m: to_float(m.get("sinr")),
    ),
    ModemSensorDescription(
        key="signal_quality",
        translation_key="signal_quality",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda m: to_float(m.get("signal_quality")),
    ),
    ModemSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=modem_temperature,
    ),
    ModemSensorDescription(
        key="data_connection",
        translation_key="data_connection",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: _text(m.get("data_conn_state")),
    ),
    ModemSensorDescription(
        key="sim_state",
        translation_key="sim_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: _text(m.get("simstate")),
    ),
    ModemSensorDescription(
        key="active_sim",
        translation_key="active_sim",
        value_fn=lambda m: to_float(m.get("active_sim")),
        suggested_display_precision=0,
    ),
    ModemSensorDescription(
        key="received",
        translation_key="received",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda m: to_float(m.get("rxbytes")),
    ),
    ModemSensorDescription(
        key="sent",
        translation_key="sent",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda m: to_float(m.get("txbytes")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        TeltonikaRouterSensor(coordinator, description)
        for description in ROUTER_SENSORS
    )
    if coordinator.vpn_host:
        async_add_entities([TeltonikaRouterSensor(coordinator, VPN_LATENCY_SENSOR)])
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                description.key,
                lambda desc=description: TeltonikaRouterSensor(c, desc),
            )
            for description in GPS_SENSORS
            if c.data.gps_available
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                ROUTER_TIME_SENSOR.key,
                lambda: TeltonikaRouterSensor(c, ROUTER_TIME_SENSOR),
            ),
        )
        if c.data.router_time is not None
        else (),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("firmware_state", lambda: TeltonikaFirmwareStateSensor(c)),)
            if c.data.firmware is not None
            else ()
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("last_sms", lambda: TeltonikaLastSmsSensor(c)),)
            if c.data.sms is not None
            else ()
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("last_action", lambda: TeltonikaLastActionSensor(c)),)
            if c.data.wireless_devices
            else ()
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (("sms_messages", lambda: TeltonikaSmsSensor(c)),)
            if c.data.sms is not None
            else ()
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                description.key,
                lambda desc=description: TeltonikaRouterSensor(c, desc),
            )
            for description in SYSTEM_SENSORS
            if c.data.system_usage is not None
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                DHCP_CLIENTS_SENSOR.key,
                lambda: TeltonikaRouterSensor(c, DHCP_CLIENTS_SENSOR),
            ),
        )
        if c.data.dhcp_leases is not None
        else (),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"vpn_{tunnel.tunnel_id}_{description.key}",
                lambda t=tunnel.tunnel_id, desc=description: TeltonikaTunnelSensor(
                    c, t, desc
                ),
            )
            for tunnel in c.data.vpn_tunnels
            for description in TUNNEL_SENSORS
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                OPEN_PORT_FORWARDS_SENSOR.key,
                lambda: TeltonikaRouterSensor(c, OPEN_PORT_FORWARDS_SENSOR),
            ),
        )
        if c.data.port_forwards
        else (),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                OPEN_INTERNET_RULES_SENSOR.key,
                lambda: TeltonikaRouterSensor(c, OPEN_INTERNET_RULES_SENSOR),
            ),
        )
        if c.data.traffic_rules
        else (),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"failover_{interface.interface_id}",
                lambda i=interface.interface_id: TeltonikaFailoverSensor(c, i),
            )
            for interface in c.data.failover
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"data_limit_{limit.interface_id}_{description.key}",
                lambda i=limit.interface_id, desc=description: TeltonikaDataLimitSensor(
                    c, i, desc
                ),
            )
            for limit in c.data.data_limits
            for description in DATA_LIMIT_SENSORS
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"data_usage_{description.key}",
                lambda desc=description: TeltonikaDataUsageSensor(c, desc),
            )
            for description in DATA_USAGE_SENSORS
            if description.value_fn(c.data) is not None
        ),
    )
    async_add_discovered(
        entry,
        async_add_entities,
        lambda c: (
            (
                f"{modem_id}_{description.key}",
                lambda m=modem_id, desc=description: TeltonikaModemSensor(c, m, desc),
            )
            for modem_id in c.modem_ids()
            for description in MODEM_SENSORS
        ),
    )


@dataclass(frozen=True, kw_only=True)
class DataUsageSensorDescription(SensorEntityDescription):
    """Describes the mobile data used today or this month."""

    value_fn: Callable[[TeltonikaData], DataUsage | None]


DATA_USAGE_SENSORS: tuple[DataUsageSensorDescription, ...] = (
    DataUsageSensorDescription(
        key="today",
        translation_key="data_today",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=0,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.data_today,
    ),
    DataUsageSensorDescription(
        key="month",
        translation_key="data_month",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.data_month,
    ),
)


class TeltonikaDataUsageSensor(TeltonikaEntity, SensorEntity):
    """The mobile data (received plus sent) of today or of this month.

    The router sums the traffic itself and starts a new day at local midnight,
    so the value falls back to zero there and long-term statistics treat that
    as a new period.
    """

    entity_description: DataUsageSensorDescription

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        description: DataUsageSensorDescription,
    ) -> None:
        super().__init__(coordinator, f"data_usage_{description.key}")
        self.entity_description = description

    @property
    def usage(self) -> DataUsage | None:
        """Return the current usage of this period."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return False if the router stopped answering this page."""
        return super().available and self.usage is not None

    @property
    def native_value(self) -> StateType:
        """Return received plus sent bytes."""
        usage = self.usage
        return usage.total if usage else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the received and sent part in megabytes."""
        usage = self.usage
        if usage is None:
            return None
        return {
            "received_mb": round(usage.received / 1_000_000, 1),
            "sent_mb": round(usage.sent / 1_000_000, 1),
        }


@dataclass(frozen=True, kw_only=True)
class DataLimitSensorDescription(SensorEntityDescription):
    """Describes a sensor of a data limit."""

    value_fn: Callable[[DataLimit], StateType | datetime]


DATA_LIMIT_SENSORS: tuple[DataLimitSensorDescription, ...] = (
    DataLimitSensorDescription(
        key="used",
        translation_key="data_limit_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda limit: limit.used,
    ),
    DataLimitSensorDescription(
        key="limit",
        translation_key="data_limit",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda limit: limit.limit,
    ),
    DataLimitSensorDescription(
        key="percent",
        translation_key="data_limit_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda limit: limit.used_percent,
    ),
    DataLimitSensorDescription(
        key="resets_at",
        translation_key="data_limit_resets_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda limit: limit.resets_at,
    ),
)


class TeltonikaDataLimitSensor(TeltonikaEntity, SensorEntity):
    """The used data, the limit or the reset time of a mobile data limit."""

    entity_description: DataLimitSensorDescription

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        interface_id: str,
        description: DataLimitSensorDescription,
    ) -> None:
        super().__init__(coordinator, f"data_limit_{interface_id}_{description.key}")
        self.entity_description = description
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
    def native_value(self) -> StateType | datetime:
        """Return the value."""
        limit = self.limit
        return self.entity_description.value_fn(limit) if limit else None


class TeltonikaFailoverSensor(TeltonikaEntity, SensorEntity):
    """The failover state of an uplink: online, offline, standby and so on."""

    _attr_translation_key = "failover"

    def __init__(self, coordinator: TeltonikaCoordinator, interface_id: str) -> None:
        super().__init__(coordinator, f"failover_{interface_id}")
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
    def native_value(self) -> str | None:
        """Return the state the router reports."""
        interface = self.interface
        return interface.status if interface else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the health score and the times the router counts."""
        interface = self.interface
        if interface is None:
            return None
        return {
            "score": interface.score,
            "seconds_since_change": interface.age,
            "seconds_online": interface.seconds_online,
            "seconds_offline": interface.seconds_offline,
            "tracking_lost": interface.lost,
        }


@dataclass(frozen=True, kw_only=True)
class TunnelSensorDescription(SensorEntityDescription):
    """Describes a sensor of a VPN tunnel."""

    value_fn: Callable[[VpnTunnel], StateType]


TUNNEL_SENSORS: tuple[TunnelSensorDescription, ...] = (
    TunnelSensorDescription(
        key="received",
        translation_key="tunnel_received",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda t: t.rx_bytes,
    ),
    TunnelSensorDescription(
        key="sent",
        translation_key="tunnel_sent",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda t: t.tx_bytes,
    ),
)


class TeltonikaTunnelSensor(TeltonikaTunnelEntity, SensorEntity):
    """A traffic counter of a VPN tunnel."""

    entity_description: TunnelSensorDescription

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        tunnel_id: str,
        description: TunnelSensorDescription,
    ) -> None:
        super().__init__(coordinator, tunnel_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the counter."""
        tunnel = self.tunnel
        return self.entity_description.value_fn(tunnel) if tunnel else None


class TeltonikaSmsSensor(TeltonikaEntity, SensorEntity):
    """The number of SMS stored on the router, with the newest ones as an attribute.

    The attribute ``messages`` lists the newest messages for a dashboard card.
    It is left out of the recorder, so the texts do not end up in the history
    database; the state machine holds them like any other attribute.
    """

    _attr_translation_key = "sms_messages"
    _attr_icon = "mdi:message-text"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"messages"})

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "sms_messages")

    @property
    def native_value(self) -> int | None:
        """Return how many messages the inbox holds."""
        sms = self.coordinator.data.sms
        return len(sms) if sms is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the newest messages, newest first."""
        sms = self.coordinator.data.sms
        if sms is None:
            return None
        return {
            "messages": [
                {
                    "sender": message.sender,
                    "date": message.date,
                    "status": message.status,
                    "message": message.message,
                }
                for message in newest_sms(sms, SMS_INBOX_SIZE)
            ]
        }


class TeltonikaLastActionSensor(TeltonikaEntity, SensorEntity):
    """The result of the last Wi-Fi scan, add or remove."""

    _attr_translation_key = "last_action"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "last_action")

    @property
    def native_value(self) -> str | None:
        """Return the message, cut to the length Home Assistant allows."""
        message = self.coordinator.last_action
        return message[:255] if message else None


class TeltonikaFirmwareStateSensor(TeltonikaEntity, SensorEntity):
    """Where the firmware update stands, from download to installation.

    The sensor stays available while the router restarts for an installation,
    so it can say so instead of turning unavailable with everything else.
    """

    _attr_translation_key = "firmware_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = FIRMWARE_STATES

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "firmware_state")

    @property
    def available(self) -> bool:
        """Return True also while an installation we started is running."""
        return super().available or self.coordinator.installing_since is not None

    @property
    def native_value(self) -> str | None:
        """Return the state, for example ``downloading`` or ``installing``."""
        return self.coordinator.firmware_state

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the download percent and the versions."""
        data = self.coordinator.data
        if data is None or data.firmware is None:
            return None
        attributes: dict[str, Any] = {
            "installed_version": data.firmware.installed,
            "latest_version": data.firmware.latest,
        }
        if data.firmware_download is not None:
            attributes["percent"] = data.firmware_download.percent
        return attributes


class TeltonikaLastSmsSensor(TeltonikaEntity, SensorEntity):
    """The result of the last SMS sent with the SMS entities."""

    _attr_translation_key = "last_sms"

    def __init__(self, coordinator: TeltonikaCoordinator) -> None:
        super().__init__(coordinator, "last_sms")

    @property
    def native_value(self) -> str | None:
        """Return the result, cut to the length Home Assistant allows."""
        message = self.coordinator.last_sms
        return message[:255] if message else None


class TeltonikaRouterSensor(TeltonikaEntity, SensorEntity):
    """A sensor of the router."""

    entity_description: RouterSensorDescription

    def __init__(
        self, coordinator: TeltonikaCoordinator, description: RouterSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data) or None


class TeltonikaModemSensor(TeltonikaModemEntity, SensorEntity):
    """A sensor of a modem.

    A counter that suddenly falls is held for a few readings, see
    :func:`guard_counter`, so a single wrong reading of 0 does not count as a
    reset in the long-term statistics.
    """

    entity_description: ModemSensorDescription

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        modem_id: str,
        description: ModemSensorDescription,
    ) -> None:
        super().__init__(coordinator, modem_id, description.key)
        self.entity_description = description
        self._counter = description.state_class == SensorStateClass.TOTAL_INCREASING
        self._last_good: float | None = None
        self._pending = 0
        self._value: StateType = self._read()
        if self._counter and isinstance(self._value, float):
            self._last_good = self._value

    def _read(self) -> StateType:
        modem = self.modem
        return self.entity_description.value_fn(modem) if modem else None

    @callback
    def _handle_coordinator_update(self) -> None:
        value = self._read()
        if self._counter and (value is None or isinstance(value, float)):
            value, self._pending = guard_counter(self._last_good, value, self._pending)
            if value is not None:
                self._last_good = value
        self._value = value
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self._value
