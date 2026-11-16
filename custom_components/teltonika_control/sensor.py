"""Sensors for Teltonika routers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import BANDS, PORTAL_STATES, UPLINK_KINDS
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity, TeltonikaModemEntity, async_add_discovered
from .models import TeltonikaData, modem_temperature, to_float

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
        value_fn=lambda m: to_float(m.get("rxbytes")),
    ),
    ModemSensorDescription(
        key="sent",
        translation_key="sent",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
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
    """A sensor of a modem."""

    entity_description: ModemSensorDescription

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        modem_id: str,
        description: ModemSensorDescription,
    ) -> None:
        super().__init__(coordinator, modem_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        modem = self.modem
        return self.entity_description.value_fn(modem) if modem else None
