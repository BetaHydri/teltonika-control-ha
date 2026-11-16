"""Tests for system usage, DHCP clients and WireGuard tunnels."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import DOMAIN
from custom_components.teltonika_control.models import (
    derive_system_usage,
    derive_vpn_tunnels,
)

from .conftest import entity_id, forbidden, mock_router
from .payloads import SERIAL, USAGE_STATUS, WIREGUARD_CONFIG, WIREGUARD_INTERFACE
from .test_integration import requests, setup_entry


def test_system_usage_is_derived() -> None:
    usage = derive_system_usage(USAGE_STATUS)
    assert usage is not None
    assert usage.uptime == 20117
    assert usage.cpu_load == 8.6
    assert usage.ram_usage == 39.17
    assert usage.flash_usage == 1.64
    assert usage.router_time == datetime.fromtimestamp(1794839356, UTC)


@pytest.mark.parametrize("raw", [None, {}, [], "x"])
def test_no_usage_without_data(raw: Any) -> None:
    assert derive_system_usage(raw) is None


def test_tunnels_combine_interface_and_configuration() -> None:
    tunnels = derive_vpn_tunnels(
        [
            WIREGUARD_INTERFACE,
            {"id": "lan", "proto": "static", "up": True},
        ],
        WIREGUARD_CONFIG,
    )
    by_id = {tunnel.tunnel_id: tunnel for tunnel in tunnels}
    assert set(by_id) == {"HOMEBASE", "SPARE"}
    assert by_id["HOMEBASE"].up is True
    assert by_id["HOMEBASE"].enabled is True
    assert by_id["HOMEBASE"].rx_bytes == 4088912
    # A disabled instance has no interface at all.
    assert by_id["SPARE"].up is False
    assert by_id["SPARE"].enabled is False


def test_tunnel_without_configuration_cannot_be_switched() -> None:
    (tunnel,) = derive_vpn_tunnels([WIREGUARD_INTERFACE], [])
    assert tunnel.up is True
    assert tunnel.enabled is None


async def test_system_sensors(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    def state(key: str) -> str:
        return hass.states.get(entity_id(hass, "sensor", key)).state

    assert float(state("uptime")) == pytest.approx(20117 / 3600, abs=0.1)
    assert float(state("cpu_load")) == 8.6
    assert float(state("ram_usage")) == 39.17
    registry = er.async_get(hass)
    assert (
        registry.async_get(entity_id(hass, "sensor", "flash_usage")).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


async def test_router_time_comes_from_the_usage_status(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_router_time")
    assert entry.runtime_data.data.router_time == datetime.fromtimestamp(
        1794839356, UTC
    )


async def test_dhcp_clients_sensor(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    sensor = hass.states.get(entity_id(hass, "sensor", "dhcp_clients"))
    assert sensor.state == "2"
    assert sensor.attributes["devices"][0] == {
        "hostname": "laptop",
        "ip": "192.168.1.10",
        "interface": "lan",
    }
    assert "macaddr" not in str(sensor.attributes)


async def test_pages_without_rights_create_no_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, usage=False, dhcp=False, wireguard=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    for platform, key in (
        ("sensor", "uptime"),
        ("sensor", "cpu_load"),
        ("sensor", "dhcp_clients"),
        ("binary_sensor", "vpn_HOMEBASE_up"),
        ("switch", "vpn_HOMEBASE_switch"),
        ("button", "vpn_HOMEBASE_reconnect"),
    ):
        assert registry.async_get_entity_id(platform, DOMAIN, f"{SERIAL}_{key}") is None


async def test_tunnel_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "binary_sensor", "vpn_HOMEBASE_up")).state == (
        STATE_ON
    )
    assert hass.states.get(entity_id(hass, "binary_sensor", "vpn_SPARE_up")).state == (
        STATE_OFF
    )
    assert hass.states.get(entity_id(hass, "switch", "vpn_HOMEBASE_switch")).state == (
        STATE_ON
    )
    assert hass.states.get(entity_id(hass, "switch", "vpn_SPARE_switch")).state == (
        STATE_OFF
    )
    assert float(hass.states.get(entity_id(hass, "sensor", "vpn_HOMEBASE_received")).state) > 0


async def test_tunnel_switch_writes_the_enabled_flag(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id(hass, "switch", "vpn_HOMEBASE_switch")},
        blocking=True,
    )

    put = requests(aioclient_mock, "PUT", "/wireguard/config/HOMEBASE")
    assert [call[2] for call in put] == [{"data": {"enabled": "0"}}]


async def test_reconnect_switches_the_tunnel_off_and_on(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "vpn_HOMEBASE_reconnect")},
        blocking=True,
    )

    put = requests(aioclient_mock, "PUT", "/wireguard/config/HOMEBASE")
    assert [call[2] for call in put] == [
        {"data": {"enabled": "0"}},
        {"data": {"enabled": "1"}},
    ]


async def test_reconnect_of_a_disabled_tunnel_is_refused(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError, match="switched off"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id(hass, "button", "vpn_SPARE_reconnect")},
            blocking=True,
        )
    assert not requests(aioclient_mock, "PUT", "/wireguard/config/SPARE")


async def test_tunnel_without_configuration_is_watched_only(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    forbidden(aioclient_mock, "/wireguard/config")
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{SERIAL}_vpn_HOMEBASE_up"
    )
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_vpn_HOMEBASE_received")
    assert registry.async_get_entity_id("switch", DOMAIN, f"{SERIAL}_vpn_HOMEBASE_switch") is None
    assert (
        registry.async_get_entity_id("button", DOMAIN, f"{SERIAL}_vpn_HOMEBASE_reconnect")
        is None
    )
