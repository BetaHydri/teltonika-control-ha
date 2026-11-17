"""Failover state, data limit and port forward switches."""

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
    derive_data_limits,
    derive_failover,
    derive_port_forwards,
)

from .conftest import entity_id, mock_router
from .payloads import (
    DATA_LIMIT_STATUS,
    FAILOVER_STATUS,
    INTERFACES_CONFIG,
    PORT_FORWARDS,
    SERIAL,
)
from .test_integration import requests, setup_entry


def test_failover_is_read_from_the_dictionary() -> None:
    interfaces = derive_failover(FAILOVER_STATUS, {"wan2"})
    assert [(i.interface_id, i.label, i.status, i.online) for i in interfaces] == [
        ("mob1s1a1", "Mobile (mob1s1a1)", "online", True),
        ("wan2", "Wi-Fi (wan2)", "offline", False),
    ]
    assert (interfaces[0].score, interfaces[0].age) == (6.0, 2)
    assert (interfaces[0].seconds_online, interfaces[0].lost) == (3600, 0)
    assert interfaces[1].seconds_offline == 66649


@pytest.mark.parametrize("raw", [None, [], "x", {"wan": "x"}, {"wan": {"enabled": False}}])
def test_failover_without_usable_data(raw: Any) -> None:
    assert derive_failover(raw) == []


def test_failover_without_status_text() -> None:
    (interface,) = derive_failover({"wan": {"enabled": True}})
    assert interface.status is None
    assert interface.online is None


def test_data_limit_is_derived() -> None:
    (limit,) = derive_data_limits(DATA_LIMIT_STATUS, INTERFACES_CONFIG)
    assert limit.interface_id == "mob1s1a1"
    assert limit.label == "SIM 1"
    assert limit.used == 2_000_000_000
    assert limit.limit == 10_000_000_000
    assert limit.used_percent == 20.0
    assert limit.reached is False
    assert limit.resets_at == datetime.fromtimestamp(1796000000, UTC)


def test_data_limit_reached_and_unknown_slot() -> None:
    raw = [
        {
            "interface": "mob9",
            "enabled": "1",
            "data_limit": 1000,
            "data_used": "1500",
        }
    ]
    (limit,) = derive_data_limits(raw, [])
    assert limit.label == "mob9"
    assert limit.reached is True
    assert limit.used_percent == 150.0
    assert limit.resets_at is None


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [{"interface": "a", "enabled": "0", "data_limit": 5}],
        [{"interface": "a", "enabled": "1", "data_limit": 0}],
        [{"enabled": "1", "data_limit": 5}],
    ],
)
def test_data_limit_needs_an_enabled_limit(raw: Any) -> None:
    assert derive_data_limits(raw, []) == []


def test_port_forwards_are_derived() -> None:
    first, second = derive_port_forwards(PORT_FORWARDS)
    assert (first.rule_id, first.name, first.enabled) == (
        "cfg_ssh",
        "SSH to the NAS",
        True,
    )
    assert (first.protocol, first.external_port, first.internal_port) == (
        "tcp",
        "2222",
        "22",
    )
    # A rule without a name is shown by its id; the flag "0" means off.
    assert (second.name, second.enabled, second.protocol) == (
        "cfg_web",
        False,
        "tcp, udp",
    )


def test_port_forward_without_flag_is_on() -> None:
    (rule,) = derive_port_forwards([{"id": "x"}])
    assert rule.enabled is True


async def test_failover_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "sensor", "failover_mob1s1a1")).state == (
        "online"
    )
    offline = hass.states.get(entity_id(hass, "sensor", "failover_wan2"))
    assert offline.state == "offline"
    assert offline.attributes["tracking_lost"] == 3
    assert hass.states.get(
        entity_id(hass, "binary_sensor", "failover_mob1s1a1_online")
    ).state == (STATE_ON)
    assert hass.states.get(
        entity_id(hass, "binary_sensor", "failover_wan2_online")
    ).state == (STATE_OFF)
    registry = er.async_get(hass)
    # The LAN is not part of the failover configuration.
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_failover_lan") is None


async def test_data_limit_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    used = hass.states.get(entity_id(hass, "sensor", "data_limit_mob1s1a1_used"))
    assert float(used.state) == pytest.approx(2.0)
    assert used.attributes["unit_of_measurement"] == "GB"
    assert float(
        hass.states.get(entity_id(hass, "sensor", "data_limit_mob1s1a1_percent")).state
    ) == pytest.approx(20.0)
    assert hass.states.get(
        entity_id(hass, "binary_sensor", "data_limit_mob1s1a1_reached")
    ).state == (STATE_OFF)
    registry = er.async_get(hass)
    # The second SIM has no limit enabled on the router.
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_data_limit_mob1s2a1_used")
        is None
    )


async def test_new_pages_are_optional(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, port_forwards=False, failover=False, data_limit=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_failover_wan2") is None
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_data_limit_mob1s1a1_used")
        is None
    )
    assert (
        registry.async_get_entity_id("switch", DOMAIN, f"{SERIAL}_port_forward_cfg_ssh")
        is None
    )
    # The rest keeps working.
    assert hass.states.get(entity_id(hass, "switch", "2-1.1_roaming_sim1")) is not None


async def test_port_forward_switches_show_the_router_setting(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    ssh = hass.states.get(entity_id(hass, "switch", "port_forward_cfg_ssh"))
    assert ssh.state == STATE_ON
    assert ssh.attributes["external_port"] == "2222"
    assert ssh.attributes["internal_port"] == "22"
    assert hass.states.get(entity_id(hass, "switch", "port_forward_cfg_web")).state == (
        STATE_OFF
    )


@pytest.fixture
def router_rules(monkeypatch: pytest.MonkeyPatch):
    """Let the router remember the flag of a port forward after a write."""
    state = {rule["id"]: rule["enabled"] for rule in PORT_FORWARDS}
    writes: list[tuple[str, str]] = []

    def install(coordinator: Any, *, apply: bool = True) -> list[tuple[str, str]]:
        client = coordinator.client

        async def read() -> list[dict[str, Any]]:
            return [{**rule, "enabled": state[rule["id"]]} for rule in PORT_FORWARDS]

        async def write(rule_id: str, enabled: bool) -> None:
            value = "1" if enabled else "0"
            writes.append((rule_id, value))
            if apply:
                state[rule_id] = value

        monkeypatch.setattr(client, "async_port_forwards_config", read)
        monkeypatch.setattr(client, "async_set_port_forward_enabled", write)
        return writes

    return install


async def test_port_forward_change_is_confirmed_by_reading_back(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    router_rules: Any,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    writes = router_rules(entry.runtime_data)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, "switch", "port_forward_cfg_web")},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id(hass, "switch", "port_forward_cfg_ssh")},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert writes == [("cfg_web", "1"), ("cfg_ssh", "0")]
    assert hass.states.get(entity_id(hass, "switch", "port_forward_cfg_web")).state == (
        STATE_ON
    )
    assert hass.states.get(entity_id(hass, "switch", "port_forward_cfg_ssh")).state == (
        STATE_OFF
    )


async def test_port_forward_writes_only_the_flag(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    # The mocked router does not remember writes, so the read-back fails; the
    # request itself is what this test looks at.
    with pytest.raises(HomeAssistantError, match="did not apply"):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id(hass, "switch", "port_forward_cfg_web")},
            blocking=True,
        )
    put = requests(aioclient_mock, "PUT", "/firewall/port_forwards/config/cfg_web")
    assert [call[2] for call in put] == [{"data": {"enabled": "1"}}]


async def test_unknown_port_forward_is_refused(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError, match="not found"):
        await entry.runtime_data.async_set_port_forward("nope", True)
