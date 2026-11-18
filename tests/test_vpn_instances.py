"""Tests for Tailscale, OpenVPN, IPsec and SSTP instances."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.models import (
    derive_vpn_instances,
    vpn_status_connected,
)

from .conftest import entity_id, mock_router
from .test_integration import requests, setup_entry

TAILSCALE = {
    "config": [{"id": "tailscale", "enabled": "1", "auth_type": "authkey"}],
    "status": [
        {
            "status": "Running",
            "url": "https://login.example",
            "ip": ["100.64.0.1"],
            "version": "1.60.1",
            "peers": {"online": 2, "total": 5},
        }
    ],
}
OPENVPN = {
    "config": [
        {"id": "office", "name": "office", "type": "client", "enable": "1"},
        {"id": "spare", "name": "spare", "type": "client", "enable": "0"},
    ],
    "status": {"office": {"status": "Connected", "uptime": 120, "rx": 10, "tx": 20}},
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Running", True),
        ("CONNECTED", True),
        ("Established", True),
        ("up", True),
        ("Stopped", False),
        ("Disconnected", False),
        ("NeedsLogin", False),
        ("Not connected", False),
        ("down", False),
        ("Connecting", None),
        ("Starting", None),
        ("", None),
        (None, None),
        (True, True),
    ],
)
def test_status_text_is_read_by_words(text: Any, expected: bool | None) -> None:
    assert vpn_status_connected(text) is expected


def test_tailscale_status_without_id_is_paired_with_its_configuration() -> None:
    (instance,) = derive_vpn_instances(
        "tailscale", "Tailscale", "enabled", TAILSCALE["config"], TAILSCALE["status"]
    )
    assert instance.label == "Tailscale"
    assert instance.enabled is True
    assert instance.connected is True
    assert instance.status == "Running"
    assert instance.details == {"version": "1.60.1", "peers_online": 2, "peers_total": 5}


def test_status_keyed_by_instance_and_missing_rows() -> None:
    by_id = {
        instance.instance_id: instance
        for instance in derive_vpn_instances(
            "openvpn", "OpenVPN", "enable", OPENVPN["config"], OPENVPN["status"]
        )
    }
    assert by_id["office"].connected is True
    assert by_id["office"].label == "OpenVPN office"
    assert by_id["office"].details == {"uptime": 120, "rx": 10, "tx": 20}
    # Switched off: not connected, whatever the status page says.
    assert by_id["spare"].enabled is False
    assert by_id["spare"].connected is False


def test_status_list_with_ids_and_status_keyed_by_name() -> None:
    listed = derive_vpn_instances(
        "openvpn",
        "OpenVPN",
        "enable",
        [{"id": "a", "enable": "1"}],
        [{"id": "a", "status": "Disconnected"}],
    )
    assert listed[0].connected is False
    by_name = derive_vpn_instances(
        "ipsec",
        "IPsec",
        "enabled",
        [{"id": "cfg1", "name": "site", "enabled": "1"}],
        {"site": {"status": "Established"}},
    )
    assert by_name[0].connected is True


def test_enabled_instance_without_a_status_row_is_down_but_unknown_without_the_page() -> None:
    config = [{"id": "a", "name": "a", "enabled": "1"}]
    assert derive_vpn_instances("ipsec", "IPsec", "enabled", config, [])[0].connected is False
    assert derive_vpn_instances("ipsec", "IPsec", "enabled", config, None)[0].connected is None


def test_instance_without_enable_flag_cannot_be_switched() -> None:
    (instance,) = derive_vpn_instances("sstp", "SSTP", "enabled", [{"id": "x"}], [])
    assert instance.enabled is None


def test_nothing_without_configuration() -> None:
    assert derive_vpn_instances("openvpn", "OpenVPN", "enable", None, {"a": {}}) == []
    assert derive_vpn_instances("openvpn", "OpenVPN", "enable", [], []) == []


async def test_router_without_these_vpns_has_no_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    unique_ids = [e.unique_id for e in er.async_get(hass).entities.values()]
    assert not [uid for uid in unique_ids if "vpnx_" in uid]


async def test_tailscale_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, vpn={"tailscale": TAILSCALE})
    await setup_entry(hass, entry)

    connected = hass.states.get(
        entity_id(hass, "binary_sensor", "vpnx_tailscale_tailscale_connected")
    )
    assert connected.state == STATE_ON
    assert connected.attributes["status"] == "Running"
    assert connected.attributes["peers_online"] == 2
    assert "ip" not in connected.attributes
    assert "url" not in connected.attributes
    assert (
        hass.states.get(entity_id(hass, "switch", "vpnx_tailscale_tailscale_switch")).state
        == STATE_ON
    )
    assert entity_id(hass, "button", "vpnx_tailscale_tailscale_reconnect")


async def test_openvpn_entities_follow_the_status(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, vpn={"openvpn": OPENVPN})
    await setup_entry(hass, entry)

    office = entity_id(hass, "binary_sensor", "vpnx_openvpn_office_connected")
    spare = entity_id(hass, "binary_sensor", "vpnx_openvpn_spare_connected")
    assert hass.states.get(office).state == STATE_ON
    assert hass.states.get(spare).state == STATE_OFF
    assert (
        hass.states.get(entity_id(hass, "switch", "vpnx_openvpn_spare_switch")).state
        == STATE_OFF
    )


async def test_switch_writes_the_flag_name_of_the_vpn_type(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, vpn={"tailscale": TAILSCALE, "openvpn": OPENVPN})
    await setup_entry(hass, entry)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id(hass, "switch", "vpnx_tailscale_tailscale_switch")},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, "switch", "vpnx_openvpn_spare_switch")},
        blocking=True,
    )

    ts = requests(aioclient_mock, "PUT", "/tailscale/config/tailscale")
    assert [call[2] for call in ts] == [{"data": {"enabled": "0"}}]
    ovpn = requests(aioclient_mock, "PUT", "/openvpn/config/spare")
    assert [call[2] for call in ovpn] == [{"data": {"enable": "1"}}]


async def test_reconnect_switches_the_instance_off_and_on(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, vpn={"tailscale": TAILSCALE})
    await setup_entry(hass, entry)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "vpnx_tailscale_tailscale_reconnect")},
        blocking=True,
    )

    put = requests(aioclient_mock, "PUT", "/tailscale/config/tailscale")
    assert [call[2] for call in put] == [
        {"data": {"enabled": "0"}},
        {"data": {"enabled": "1"}},
    ]


async def test_reconnect_of_a_disabled_instance_is_refused(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, vpn={"openvpn": OPENVPN})
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError, match="switched off"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id(hass, "button", "vpnx_openvpn_spare_reconnect")},
            blocking=True,
        )
    assert not requests(aioclient_mock, "PUT", "/openvpn/config/spare")


async def test_status_page_missing_leaves_the_state_unknown(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, vpn={"openvpn": {"config": OPENVPN["config"]}})
    await setup_entry(hass, entry)

    office = entity_id(hass, "binary_sensor", "vpnx_openvpn_office_connected")
    assert hass.states.get(office).state == STATE_UNKNOWN
