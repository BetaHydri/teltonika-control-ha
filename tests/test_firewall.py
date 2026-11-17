"""Traffic rule switches, firewall counters and groups."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import DOMAIN
from custom_components.teltonika_control.models import (
    TRAFFIC_GROUP_ACCESS,
    TRAFFIC_GROUP_FORWARD,
    TRAFFIC_GROUP_OTHER,
    TRAFFIC_GROUP_SYSTEM,
    derive_traffic_rules,
    traffic_rule_group,
)

from .conftest import entity_id, mock_router
from .payloads import SERIAL, TRAFFIC_RULES
from .test_integration import requests, setup_entry


def test_traffic_rules_are_sorted_into_groups() -> None:
    rules = {rule.name: rule for rule in derive_traffic_rules(TRAFFIC_RULES)}
    assert rules["Allow-Ping"].group == TRAFFIC_GROUP_SYSTEM
    assert rules["Allow-mDNS"].group == TRAFFIC_GROUP_SYSTEM
    assert rules["Enable_SSH_WAN"].group == TRAFFIC_GROUP_ACCESS
    assert rules["ha-gcs"].group == TRAFFIC_GROUP_ACCESS
    assert rules["ha-gcs-ipv4-forward"].group == TRAFFIC_GROUP_FORWARD
    assert rules["Block-telnet"].group == TRAFFIC_GROUP_OTHER


def test_traffic_rule_details() -> None:
    rules = {rule.name: rule for rule in derive_traffic_rules(TRAFFIC_RULES)}
    ssh = rules["Enable_SSH_WAN"]
    assert (ssh.rule_id, ssh.enabled, ssh.source, ssh.destination) == (
        "15",
        False,
        "wan",
        None,
    )
    assert (ssh.protocol, ssh.ports, ssh.action) == ("tcp", "22", "ACCEPT")
    forward = rules["ha-gcs-ipv4-forward"]
    assert (forward.destination, forward.protocol) == ("lan", "tcp, udp")


def test_only_enabled_rules_that_let_the_internet_in_count() -> None:
    rules = {rule.name: rule for rule in derive_traffic_rules(TRAFFIC_RULES)}
    assert rules["ha-gcs"].opens_internet is True
    assert rules["ha-gcs-ipv4-forward"].opens_internet is True
    assert rules["Enable_SSH_WAN"].opens_internet is False  # switched off
    assert rules["Allow-Ping"].opens_internet is False  # the router's own rule
    assert rules["Block-telnet"].opens_internet is False  # rejects traffic


@pytest.mark.parametrize(
    ("name", "src", "dest", "target", "group"),
    [
        ("x", "lan", None, "ACCEPT", TRAFFIC_GROUP_OTHER),
        ("x", None, None, "ACCEPT", TRAFFIC_GROUP_OTHER),
        ("x", "wan", None, "DROP", TRAFFIC_GROUP_OTHER),
        ("x", "wan", None, "accept", TRAFFIC_GROUP_ACCESS),
        ("x", "wireguard", "lan", "ACCEPT", TRAFFIC_GROUP_FORWARD),
        ("Allow-x", "wan", None, "ACCEPT", TRAFFIC_GROUP_SYSTEM),
    ],
)
def test_traffic_rule_group(
    name: str, src: str | None, dest: str | None, target: str, group: str
) -> None:
    assert traffic_rule_group(name, src, dest, target) == group


def test_traffic_rules_without_data() -> None:
    assert derive_traffic_rules(None) == []
    assert derive_traffic_rules([{"name": "no id"}]) == []
    (rule,) = derive_traffic_rules([{"id": "1"}])
    assert (rule.name, rule.enabled, rule.group) == ("1", True, TRAFFIC_GROUP_OTHER)


async def test_traffic_rule_switches(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    ssh = hass.states.get(entity_id(hass, "switch", "traffic_rule_15"))
    assert ssh.state == STATE_OFF
    assert ssh.attributes["kind"] == "traffic_rule"
    assert ssh.attributes["group"] == TRAFFIC_GROUP_ACCESS
    assert (ssh.attributes["protocol"], ssh.attributes["ports"]) == ("tcp", "22")
    assert hass.states.get(entity_id(hass, "switch", "traffic_rule_21")).state == (
        STATE_ON
    )
    forward = hass.states.get(entity_id(hass, "switch", "traffic_rule_45"))
    assert forward.attributes["destination_zone"] == "lan"


async def test_the_routers_own_rules_are_disabled_by_default(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    ping = registry.async_get_entity_id("switch", DOMAIN, f"{SERIAL}_traffic_rule_6")
    assert ping is not None
    assert registry.async_get(ping).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(ping) is None
    # A rule you made yourself is shown at once.
    assert registry.async_get(entity_id(hass, "switch", "traffic_rule_21")).disabled_by is None


async def test_firewall_counters(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    forwards = hass.states.get(entity_id(hass, "sensor", "open_port_forwards"))
    assert forwards.state == "1"
    assert forwards.attributes["rules"] == ["SSH to the NAS"]
    rules = hass.states.get(entity_id(hass, "sensor", "open_internet_rules"))
    assert rules.state == "2"
    assert rules.attributes["rules"] == ["ha-gcs", "ha-gcs-ipv4-forward"]


async def test_firewall_pages_are_optional(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, port_forwards=False, traffic_rules=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    for platform, key in (
        ("switch", "traffic_rule_21"),
        ("switch", "port_forward_cfg_ssh"),
        ("sensor", "open_port_forwards"),
        ("sensor", "open_internet_rules"),
    ):
        assert registry.async_get_entity_id(platform, DOMAIN, f"{SERIAL}_{key}") is None


@pytest.fixture
def router_rules(monkeypatch: pytest.MonkeyPatch):
    """Let the router remember the flag of a traffic rule after a write."""
    state = {rule["id"]: rule["enabled"] for rule in TRAFFIC_RULES}
    writes: list[tuple[str, str]] = []

    def install(coordinator: Any) -> list[tuple[str, str]]:
        client = coordinator.client

        async def read() -> list[dict[str, Any]]:
            return [{**rule, "enabled": state[rule["id"]]} for rule in TRAFFIC_RULES]

        async def write(rule_id: str, enabled: bool) -> None:
            value = "1" if enabled else "0"
            writes.append((rule_id, value))
            state[rule_id] = value

        monkeypatch.setattr(client, "async_traffic_rules_config", read)
        monkeypatch.setattr(client, "async_set_traffic_rule_enabled", write)
        return writes

    return install


async def test_traffic_rule_change_is_confirmed_by_reading_back(
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
        {"entity_id": entity_id(hass, "switch", "traffic_rule_15")},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert writes == [("15", "1")]
    assert hass.states.get(entity_id(hass, "switch", "traffic_rule_15")).state == (
        STATE_ON
    )
    assert hass.states.get(entity_id(hass, "sensor", "open_internet_rules")).state == "3"


async def test_traffic_rule_writes_only_the_flag(
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
            {"entity_id": entity_id(hass, "switch", "traffic_rule_15")},
            blocking=True,
        )
    put = requests(aioclient_mock, "PUT", "/firewall/traffic_rules/config/15")
    assert [call[2] for call in put] == [{"data": {"enabled": "1"}}]


async def test_unknown_traffic_rule_is_refused(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError, match="not found"):
        await entry.runtime_data.async_set_traffic_rule("nope", True)
