"""Tests for setup, entities, actions and services."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.teltonika_control.const import DOMAIN, EVENT_PORTAL_RESULT

from .conftest import (
    entity_id,
    find_device,
    mock_login_failure,
    mock_router,
    mock_unreachable,
    router_device_id,
)
from .payloads import BASE, SCAN_RESULT, SERIAL, WIRELESS_CONFIG, payloads


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


def requests(aioclient_mock: Any, method: str, suffix: str) -> list[Any]:
    return [
        c
        for c in aioclient_mock.mock_calls
        if c[0] == method and str(c[1]).split("?")[0].endswith(suffix)
    ]


async def test_entities_reflect_the_router(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    def state(platform: str, key: str) -> str:
        return hass.states.get(entity_id(hass, platform, key)).state

    assert state("sensor", "uplink") == "mobile"
    assert state("sensor", "uplink_ip") == "10.1.2.3"
    assert state("sensor", "wifi_ssid") == "CampWifi"
    assert float(state("sensor", "wifi_signal")) == -61
    assert float(state("sensor", "wifi_bitrate")) == 78
    assert state("sensor", "wifi_band") == "2.4 GHz"
    # The Wi-Fi is connected, but the router's failover calls it offline.
    assert state("sensor", "portal_state") == "login_required"
    assert state("binary_sensor", "wifi_connected") == STATE_ON
    assert state("binary_sensor", "internet") == STATE_ON
    assert state("binary_sensor", "login_required") == STATE_ON
    assert float(state("sensor", "2-1.1_rsrp")) == -104
    assert float(state("sensor", "2-1.1_temperature")) == 45
    assert state("sensor", "2-1.1_operator") == "Testnet"
    assert state("binary_sensor", "2-1.1_mobile_connected") == STATE_ON
    assert state("select", "priority") == "mobile_first"
    assert state("select", "2-1.1_sim") == "sim_1"
    assert state("switch", "ap_default_radio0") == STATE_ON
    assert state("switch", "ap_default_radio1") == STATE_OFF


async def test_wifi_without_internet_shows_login_required(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, wifi_metric=0, internet=False)
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "sensor", "uplink")).state == "wifi"
    assert hass.states.get(entity_id(hass, "sensor", "portal_state")).state == (
        "login_required"
    )
    assert hass.states.get(entity_id(hass, "binary_sensor", "login_required")).state == (
        STATE_ON
    )
    assert hass.states.get(entity_id(hass, "binary_sensor", "internet")).state == (
        STATE_OFF
    )


async def test_buttons_call_the_router(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    for key, suffix in (
        ("reboot", "/system/actions/reboot"),
        ("2-1.1_restart_mobile", "/modems/2-1.1/actions/restart_connection"),
        ("reconnect_wifi", "/wireless/actions/reconnect"),
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id(hass, "button", key)},
            blocking=True,
        )
        assert requests(aioclient_mock, "POST", suffix), key


async def test_access_point_switch_writes_enabled_flag(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, "switch", "ap_default_radio1")},
        blocking=True,
    )

    put = requests(aioclient_mock, "PUT", "/wireless/interfaces/config/default_radio1")
    assert put[0][2] == {"data": {"enabled": "1"}}


async def test_priority_select_sets_metric_and_reconnects(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", "priority"), "option": "wifi_first"},
        blocking=True,
    )

    assert requests(aioclient_mock, "PUT", "/interfaces/config/wan2")[0][2] == {
        "data": {"metric": "0"}
    }
    assert requests(aioclient_mock, "POST", "/wireless/actions/reconnect")[0][2] == {
        "data": {"sta_id": "6"}
    }


async def test_sim_select_switches_only_when_different(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    sim = entity_id(hass, "select", "2-1.1_sim")

    await hass.services.async_call(
        "select", "select_option", {"entity_id": sim, "option": "sim_1"}, blocking=True
    )
    assert not requests(aioclient_mock, "POST", "/modems/2-1.1/actions/switch_sim")

    await hass.services.async_call(
        "select", "select_option", {"entity_id": sim, "option": "sim_2"}, blocking=True
    )
    assert requests(aioclient_mock, "POST", "/modems/2-1.1/actions/switch_sim")


async def test_scan_service_returns_networks(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    aioclient_mock.post(
        f"{BASE}/wireless/actions/scan", json={"success": True, "data": SCAN_RESULT}
    )
    await setup_entry(hass, entry)

    result = await hass.services.async_call(
        DOMAIN,
        "scan_wifi",
        {"device_id": router_device_id(hass), "radio": "radio0"},
        blocking=True,
        return_response=True,
    )

    assert result["networks"] == [
        {
            "ssid": "CafeFreeWifi",
            "bssid": "00:11:22:33:44:55",
            "signal": -55,
            "channel": 11,
            "band": "2.4 GHz",
            "encrypted": False,
            "security": "None",
            "radio": "radio0",
        }
    ]


async def test_portal_mode_success_fires_event(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    # Wi-Fi is the uplink and the probe answers 204: the first check succeeds.
    mock_router(aioclient_mock, wifi_metric=0, internet=True)
    await setup_entry(hass, entry)
    events: list[Any] = []
    hass.bus.async_listen(EVENT_PORTAL_RESULT, events.append)

    await hass.services.async_call(
        DOMAIN,
        "portal_mode",
        {"device_id": router_device_id(hass), "minutes": 1},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert [e.data["success"] for e in events] == [True]
    # Success keeps Wi-Fi first: only the "0" metric was written.
    metrics = [c[2]["data"]["metric"] for c in requests(aioclient_mock, "PUT", "/interfaces/config/wan2")]
    assert metrics == ["0"]


async def test_portal_mode_rolls_back_without_internet(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, wifi_metric=0, internet=False)
    await setup_entry(hass, entry)
    events: list[Any] = []
    hass.bus.async_listen(EVENT_PORTAL_RESULT, events.append)

    await hass.services.async_call(
        DOMAIN,
        "portal_mode",
        {"device_id": router_device_id(hass), "minutes": 1},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert [e.data["success"] for e in events] == [False]
    metrics = [c[2]["data"]["metric"] for c in requests(aioclient_mock, "PUT", "/interfaces/config/wan2")]
    assert metrics[0] == "0"
    assert metrics[-1] == "10"


async def test_service_with_unknown_device_is_rejected(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "portal_mode",
            {"device_id": "does-not-exist"},
            blocking=True,
        )


async def test_wrong_password_starts_reauth(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_login_failure(aioclient_mock)
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"]["source"] == "reauth"
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_unreachable_router_retries_later(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_unreachable(aioclient_mock)
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_modem_is_a_child_device_of_the_router(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    modem = find_device(hass, (DOMAIN, f"{SERIAL}_2-1.1"))

    assert modem.via_device_id == router_device_id(hass)


async def test_unload_removes_the_entry_cleanly(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


MULTI_AP_RADIO = {
    "id": "multi_radio1",
    "mode": "multi_ap",
    "device": ["radio1"],
    "network": "wifi5",
}
OK = {"success": True}


def mock_multi_ap_router(
    aioclient_mock: Any, entries: list[dict[str, Any]], **kwargs: Any
) -> None:
    """Router whose 5 GHz radio runs as Multi AP (registered before the defaults)."""
    wireless = [*deepcopy(WIRELESS_CONFIG), MULTI_AP_RADIO]
    aioclient_mock.get(
        f"{BASE}/wireless/interfaces/config", json={"success": True, "data": wireless}
    )
    aioclient_mock.get(
        f"{BASE}/wireless/multi_ap/config", json={"success": True, "data": entries}
    )
    aioclient_mock.post(f"{BASE}/wireless/multi_ap/config", json=OK)
    for entry_id in ("cfg1", "cfg2"):
        aioclient_mock.put(f"{BASE}/wireless/multi_ap/config/{entry_id}", json=OK)
        aioclient_mock.delete(f"{BASE}/wireless/multi_ap/config/{entry_id}", json=OK)
    mock_router(aioclient_mock, **kwargs)


async def test_join_on_multi_ap_radio_adds_to_the_list(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_multi_ap_router(aioclient_mock, [{"id": "cfg1", "ssid": "Home", "priority": "3"}])
    await setup_entry(hass, entry)

    await hass.services.async_call(
        DOMAIN,
        "join_wifi",
        {
            "device_id": router_device_id(hass),
            "radio": "radio1",
            "ssid": "Camp5",
            "password": "pw12345678",
        },
        blocking=True,
    )

    assert requests(aioclient_mock, "POST", "/wireless/multi_ap/config")[0][2] == {
        "data": {
            "ssid": "Camp5",
            "enabled": "1",
            "priority": "4",
            "key": "pw12345678",
        }
    }
    assert not requests(aioclient_mock, "POST", "/wireless/actions/join")


async def test_join_known_multi_ap_network_updates_the_password(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_multi_ap_router(aioclient_mock, [{"id": "cfg1", "ssid": "Home"}])
    await setup_entry(hass, entry)
    device_id = router_device_id(hass)

    await hass.services.async_call(
        DOMAIN,
        "join_wifi",
        {"device_id": device_id, "radio": "radio1", "ssid": "Home", "password": "newpass123"},
        blocking=True,
    )
    assert requests(aioclient_mock, "PUT", "/wireless/multi_ap/config/cfg1")[0][2] == {
        "data": {"key": "newpass123"}
    }

    with pytest.raises(HomeAssistantError, match="already in the Multi AP list"):
        await hass.services.async_call(
            DOMAIN,
            "join_wifi",
            {"device_id": device_id, "radio": "radio1", "ssid": "Home"},
            blocking=True,
        )


async def test_join_on_busy_radio_is_rejected(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError, match="already has a Wi-Fi client"):
        await hass.services.async_call(
            DOMAIN,
            "join_wifi",
            {
                "device_id": router_device_id(hass),
                "radio": "radio0",
                "ssid": "Other",
                "password": "pw12345678",
            },
            blocking=True,
        )

    assert not requests(aioclient_mock, "POST", "/wireless/actions/join")


async def test_forget_multi_ap_entry_by_ssid(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_multi_ap_router(
        aioclient_mock,
        [{"id": "cfg1", "ssid": "Home"}, {"id": "cfg2", "ssid": "Camp5"}],
    )
    await setup_entry(hass, entry)

    await hass.services.async_call(
        DOMAIN,
        "forget_wifi",
        {"device_id": router_device_id(hass), "ssid": "Camp5"},
        blocking=True,
    )

    assert len(requests(aioclient_mock, "DELETE", "/wireless/multi_ap/config/cfg2")) == 1
    assert not requests(aioclient_mock, "DELETE", "/wireless/multi_ap/config/cfg1")


async def test_last_multi_ap_entry_is_kept(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_multi_ap_router(aioclient_mock, [{"id": "cfg1", "ssid": "Home"}])
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError, match="last Multi AP entry"):
        await hass.services.async_call(
            DOMAIN,
            "forget_wifi",
            {"device_id": router_device_id(hass), "ssid": "Home"},
            blocking=True,
        )

    assert not requests(aioclient_mock, "DELETE", "/wireless/multi_ap/config/cfg1")


async def test_forget_by_network_id_refuses_multi_ap_radio(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_multi_ap_router(aioclient_mock, [{"id": "cfg1", "ssid": "Home"}])
    aioclient_mock.delete(f"{BASE}/wireless/interfaces/config/multi_radio1", json=OK)
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError, match="removed by SSID"):
        await hass.services.async_call(
            DOMAIN,
            "forget_wifi",
            {"device_id": router_device_id(hass), "station_id": "multi_radio1"},
            blocking=True,
        )

    assert not requests(aioclient_mock, "DELETE", "/wireless/interfaces/config/multi_radio1")


async def test_forget_needs_exactly_one_target(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    device_id = router_device_id(hass)

    for data in (
        {"device_id": device_id},
        {"device_id": device_id, "station_id": "6", "ssid": "CampWifi"},
    ):
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(DOMAIN, "forget_wifi", data, blocking=True)


async def test_forget_removes_a_self_created_interface(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    data = payloads()
    data["interfaces"][2]["id"] = "wifi4"
    data["config"][1]["id"] = "wifi4"
    aioclient_mock.get(
        f"{BASE}/interfaces/status", json={"success": True, "data": data["interfaces"]}
    )
    aioclient_mock.get(
        f"{BASE}/interfaces/config", json={"success": True, "data": data["config"]}
    )
    aioclient_mock.delete(f"{BASE}/interfaces/config/wifi4", json=OK)
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    await hass.services.async_call(
        DOMAIN,
        "forget_wifi",
        {"device_id": router_device_id(hass), "station_id": "6"},
        blocking=True,
    )

    assert len(requests(aioclient_mock, "DELETE", "/wireless/interfaces/config/6")) == 1
    assert len(requests(aioclient_mock, "DELETE", "/interfaces/config/wifi4")) == 1


async def test_gps_entities_show_the_position(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    tracker = hass.states.get(entity_id(hass, "device_tracker", "gps"))
    assert tracker.attributes["latitude"] == 48.436849
    assert tracker.attributes["longitude"] == 13.110672
    assert tracker.attributes["gps_accuracy"] == 0.6
    assert tracker.attributes["source_type"] == "gps"

    def state(key: str) -> str:
        return hass.states.get(entity_id(hass, "sensor", key)).state

    assert float(state("gps_speed")) == 4
    assert float(state("gps_altitude")) == 350
    assert float(state("gps_satellites")) == 7
    assert float(state("gps_accuracy")) == 0.6
    # Heading and fix status are disabled by default.
    registry = er.async_get(hass)
    for key in ("gps_heading", "gps_fix"):
        entity = registry.async_get(entity_id(hass, "sensor", key))
        assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_router_without_gps_has_no_gps_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, gps=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("device_tracker", DOMAIN, f"{SERIAL}_gps") is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_gps_speed") is None
    # Everything else works as before.
    assert hass.states.get(entity_id(hass, "sensor", "uplink")).state == "mobile"


async def test_gps_without_a_fix_is_unknown(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(
        aioclient_mock,
        gps={"latitude": "0", "longitude": "0", "satellites": "0", "speed": "0"},
    )
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "device_tracker", "gps")).state == "unknown"
    assert hass.states.get(entity_id(hass, "sensor", "gps_speed")).state == "unknown"


async def test_forget_keeps_a_default_interface(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)  # the Wi-Fi client uses the default interface wan2
    await setup_entry(hass, entry)

    await hass.services.async_call(
        DOMAIN,
        "forget_wifi",
        {"device_id": router_device_id(hass), "station_id": "6"},
        blocking=True,
    )

    assert len(requests(aioclient_mock, "DELETE", "/wireless/interfaces/config/6")) == 1
    assert not requests(aioclient_mock, "DELETE", "/interfaces/config/wan2")


async def test_services_accept_an_entity_of_the_router_as_target(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    aioclient_mock.post(
        f"{BASE}/wireless/actions/scan", json={"success": True, "data": SCAN_RESULT}
    )
    await setup_entry(hass, entry)

    result = await hass.services.async_call(
        DOMAIN,
        "scan_wifi",
        {"entity_id": entity_id(hass, "sensor", "uplink"), "radio": "radio0"},
        blocking=True,
        return_response=True,
    )
    assert result["networks"][0]["ssid"] == "CafeFreeWifi"

    # An entity of the modem (a child device) reaches the same router.
    await hass.services.async_call(
        DOMAIN,
        "set_priority",
        {
            "entity_id": [entity_id(hass, "select", "2-1.1_sim")],
            "wifi_first": False,
            "verify": False,
        },
        blocking=True,
    )
    assert requests(aioclient_mock, "PUT", "/interfaces/config/wan2")

    # A device id as list, as a dashboard target sends it.
    await hass.services.async_call(
        DOMAIN,
        "scan_wifi",
        {"device_id": [router_device_id(hass)], "radio": "radio0"},
        blocking=True,
        return_response=True,
    )


async def test_service_without_any_target_is_rejected(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "set_priority", {"wifi_first": True}, blocking=True
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_priority",
            {"entity_id": "sensor.not_a_router_entity", "wifi_first": True},
            blocking=True,
        )


CAMP_5GHZ = {
    "ssid": "Camp5",
    "bssid": "aa:bb:cc:dd:ee:01",
    "signal": -60,
    "channel": 36,
    "encryption": {"enabled": True},
    "encryption_description": "WPA2",
}
ALREADY_SAVED_24GHZ = {
    "ssid": "CampWifi",
    "bssid": "aa:bb:cc:dd:ee:02",
    "signal": -50,
    "channel": 6,
    "encryption": {"enabled": True},
}


def mock_scan(aioclient_mock: Any, results: dict[str, list[dict[str, Any]]]) -> None:
    """Answer a scan with the networks of the radio named in the request."""

    async def respond(method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        radio = ((data or {}).get("data") or {}).get("device")
        return AiohttpClientMockResponse(
            method, url, json={"success": True, "data": results.get(radio, [])}
        )

    aioclient_mock.post(f"{BASE}/wireless/actions/scan", side_effect=respond)


async def press(hass: HomeAssistant, entity: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity}, blocking=True)


async def test_wifi_entities_scan_and_add_a_network(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    mock_scan(aioclient_mock, {"radio0": [ALREADY_SAVED_24GHZ], "radio1": [CAMP_5GHZ]})
    aioclient_mock.post(
        f"{BASE}/wireless/actions/join", json={"success": True, "data": {}}
    )
    await setup_entry(hass, entry)
    found = entity_id(hass, "select", "found_networks")
    password = entity_id(hass, "text", "wifi_password")
    action = entity_id(hass, "sensor", "last_action")

    await press(hass, entity_id(hass, "button", "scan_wifi"))

    label = "Camp5 [5 GHz · secured · -60 dBm]"
    assert hass.states.get(found).attributes["options"] == [label]
    assert hass.states.get(found).state == label
    # The saved network of the same band is hidden.
    assert hass.states.get(action).state == "1 new networks (2 seen, 1 already saved)"

    await hass.services.async_call(
        "text", "set_value", {"entity_id": password, "value": "pw12345678"}, blocking=True
    )
    assert hass.states.get(password).state == "********"

    await press(hass, entity_id(hass, "button", "add_network"))

    assert requests(aioclient_mock, "POST", "/wireless/actions/join")[0][2] == {
        "data": {"device": "radio1", "ssid": "Camp5", "password": "pw12345678"}
    }
    assert hass.states.get(password).state == ""
    assert hass.states.get(found).attributes["options"] == []
    assert hass.states.get(action).state == "Saved Camp5"


async def test_scan_says_it_has_started_and_ignores_a_second_press(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    action = entity_id(hass, "sensor", "last_action")
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def slow_scan(radio: str | None = None) -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return []

    monkeypatch.setattr(coordinator, "async_scan_wifi", slow_scan)

    first = asyncio.create_task(coordinator.async_scan_networks())
    await started.wait()
    assert hass.states.get(action).state == "Scanning for networks ..."
    assert coordinator.scanning

    await coordinator.async_scan_networks()
    assert calls == 1

    release.set()
    await first
    assert not coordinator.scanning
    assert hass.states.get(action).state == "0 new networks (0 seen, 0 already saved)"


async def test_failed_scan_is_reported_and_can_be_repeated(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def failing_scan(radio: str | None = None) -> list[dict[str, Any]]:
        raise HomeAssistantError("radio busy")

    monkeypatch.setattr(coordinator, "async_scan_wifi", failing_scan)
    with pytest.raises(HomeAssistantError, match="radio busy"):
        await coordinator.async_scan_networks()

    assert not coordinator.scanning
    assert coordinator.last_action == "Scan failed: radio busy"


async def test_adding_needs_a_selection_and_a_password(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    mock_scan(aioclient_mock, {"radio1": [CAMP_5GHZ]})
    await setup_entry(hass, entry)
    add = entity_id(hass, "button", "add_network")

    with pytest.raises(HomeAssistantError, match="Scan for networks"):
        await press(hass, add)

    await press(hass, entity_id(hass, "button", "scan_wifi"))
    with pytest.raises(HomeAssistantError, match="at least 8"):
        await press(hass, add)

    assert not requests(aioclient_mock, "POST", "/wireless/actions/join")


async def test_saved_networks_select_and_remove_button(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    saved = entity_id(hass, "select", "saved_networks")
    remove = entity_id(hass, "button", "remove_network")
    assert hass.states.get(saved).attributes["options"] == ["CampWifi (2.4 GHz)"]

    with pytest.raises(HomeAssistantError, match="Select a saved network"):
        await press(hass, remove)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": saved, "option": "CampWifi (2.4 GHz)"},
        blocking=True,
    )
    await press(hass, remove)

    assert len(requests(aioclient_mock, "DELETE", "/wireless/interfaces/config/6")) == 1
    assert hass.states.get(entity_id(hass, "sensor", "last_action")).state == (
        "Removed CampWifi"
    )


async def test_saved_networks_include_multi_ap_entries(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_multi_ap_router(
        aioclient_mock,
        [{"id": "cfg1", "ssid": "Home"}, {"id": "cfg2", "ssid": "Camp5"}],
    )
    await setup_entry(hass, entry)
    saved = entity_id(hass, "select", "saved_networks")
    assert hass.states.get(saved).attributes["options"] == [
        "CampWifi (2.4 GHz)",
        "Home (5 GHz, Multi AP)",
        "Camp5 (5 GHz, Multi AP)",
    ]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": saved, "option": "Camp5 (5 GHz, Multi AP)"},
        blocking=True,
    )
    await press(hass, entity_id(hass, "button", "remove_network"))

    assert len(requests(aioclient_mock, "DELETE", "/wireless/multi_ap/config/cfg2")) == 1
    assert not requests(aioclient_mock, "DELETE", "/wireless/multi_ap/config/cfg1")


async def test_router_with_multi_ap_on_2_4_ghz_and_a_client_on_5_ghz(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    """The opposite of the RUTC50: Multi AP on radio0, a normal client on radio1."""
    wireless = [
        item for item in deepcopy(WIRELESS_CONFIG) if item["id"] != "6"
    ] + [
        {
            "id": "multi_radio0",
            "mode": "multi_ap",
            "device": ["radio0"],
            "network": "wifi24",
        },
        {
            "id": "7",
            "mode": "sta",
            "ssid": "Dedicated5",
            "network": "wifi5",
            "device": ["radio1"],
        },
    ]
    aioclient_mock.get(
        f"{BASE}/wireless/interfaces/config", json={"success": True, "data": wireless}
    )
    aioclient_mock.get(
        f"{BASE}/wireless/multi_ap/config",
        json={"success": True, "data": [{"id": "cfg1", "ssid": "Home"}]},
    )
    aioclient_mock.post(f"{BASE}/wireless/multi_ap/config", json=OK)
    aioclient_mock.post(f"{BASE}/wireless/actions/join", json=OK)
    mock_router(aioclient_mock)
    mock_scan(
        aioclient_mock,
        {
            "radio0": [{**CAMP_5GHZ, "ssid": "Camp24", "channel": 6}],
            "radio1": [CAMP_5GHZ],
        },
    )
    await setup_entry(hass, entry)

    # Each list is labelled with the band of its own radio.
    assert hass.states.get(entity_id(hass, "select", "saved_networks")).attributes[
        "options"
    ] == ["Dedicated5 (5 GHz)", "Home (2.4 GHz, Multi AP)"]

    await press(hass, entity_id(hass, "button", "scan_wifi"))
    found = entity_id(hass, "select", "found_networks")
    password = entity_id(hass, "text", "wifi_password")
    add = entity_id(hass, "button", "add_network")

    async def choose(prefix: str) -> None:
        option = next(
            o
            for o in hass.states.get(found).attributes["options"]
            if o.startswith(prefix)
        )
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": found, "option": option},
            blocking=True,
        )
        await hass.services.async_call(
            "text",
            "set_value",
            {"entity_id": password, "value": "pw12345678"},
            blocking=True,
        )

    # A 2.4 GHz network goes into the Multi AP list ...
    await choose("Camp24")
    await press(hass, add)
    assert requests(aioclient_mock, "POST", "/wireless/multi_ap/config")[0][2]["data"][
        "ssid"
    ] == "Camp24"
    assert not requests(aioclient_mock, "POST", "/wireless/actions/join")

    # ... while the 5 GHz radio already holds a client, so it is refused.
    await choose("Camp5")
    with pytest.raises(HomeAssistantError, match="already has a Wi-Fi client"):
        await press(hass, add)
    assert not requests(aioclient_mock, "POST", "/wireless/actions/join")


async def test_router_time_sensor_needs_a_date_header(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, date="Mon, 16 Nov 2026 12:00:00 GMT")
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    entity = registry.async_get(entity_id(hass, "sensor", "router_time"))
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_no_router_time_sensor_without_a_date_header(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, usage=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_router_time") is None
