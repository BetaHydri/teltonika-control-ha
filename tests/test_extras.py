"""Router discovery, MAC links, SMS and the firmware update information."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.teltonika_control.const import DOMAIN, EVENT_SMS_RECEIVED
from custom_components.teltonika_control.models import (
    RouterInfo,
    derive_firmware,
    derive_sms,
    firmware_version_tuple,
)

from .conftest import (
    ENTRY_DATA,
    entity_id,
    find_device,
    mock_login_failure,
    mock_router,
    mock_unreachable,
)
from .payloads import DEVICE_STATUS, FIRMWARE_UPDATES, HOST, SERIAL, SMS_MESSAGES
from .test_integration import requests, setup_entry

ROUTER_MAC = "00:1e:42:00:00:01"
NEW_HOST = "192.168.1.50"


# --- models ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("RUTC50_R_00.07.25.2", (7, 25, 2)),
        ("RUTC_R_00.07.24", (7, 24)),
        ("7.25.2", (7, 25, 2)),
        ("RUTX_R_00.07.06.1", (7, 6, 1)),
        ("", None),
        (None, None),
        ("no numbers here", None),
    ],
)
def test_firmware_versions_are_reduced_to_numbers(text, expected) -> None:
    assert firmware_version_tuple(text) == expected


def test_firmware_update_is_found_and_stable_is_preferred() -> None:
    info = derive_firmware("RUTC_R_00.07.26.2", FIRMWARE_UPDATES)
    assert info is not None
    assert info.latest == "RUTC_R_00.07.27.1"
    assert info.newest == "RUTC_R_00.07.28.1"
    assert info.update_available is True


def test_firmware_without_update_or_with_odd_versions() -> None:
    current = {"device": {"stable_version": "RUTC_R_00.07.26.2"}}
    assert derive_firmware("RUTC_R_00.07.26.2", current).update_available is False
    older = {"device": {"stable_version": "RUTC_R_00.07.20"}}
    assert derive_firmware("RUTC_R_00.07.26.2", older).update_available is False
    # Versions that cannot be compared never claim an update.
    odd = {"device": {"version": "latest"}}
    assert derive_firmware("RUTC_R_00.07.26.2", odd).update_available is None
    assert derive_firmware(None, current).update_available is None


@pytest.mark.parametrize("raw", [None, {}, {"device": {}}, {"device": "x"}, []])
def test_no_firmware_information_gives_nothing(raw) -> None:
    assert derive_firmware("RUTC_R_00.07.26.2", raw) is None


def test_sms_inbox_is_read_and_a_missing_page_is_told_apart() -> None:
    assert derive_sms(None) is None
    assert derive_sms([]) == []
    messages = derive_sms(SMS_MESSAGES + [{"message": "no id"}])
    assert [m.message_id for m in messages] == ["1", "2"]
    assert messages[1].sender == "Provider"
    assert messages[0].key != messages[1].key


def test_router_info_reads_both_mac_addresses() -> None:
    info = RouterInfo.from_device_status(HOST, DEVICE_STATUS)
    assert (info.mac, info.mac_eth) == ("001E42000001", "001E42000002")


# --- device registry --------------------------------------------------------


async def test_router_device_has_its_mac_addresses(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    device = find_device(hass, (DOMAIN, SERIAL))
    assert device.connections == {
        (CONNECTION_NETWORK_MAC, ROUTER_MAC),
        (CONNECTION_NETWORK_MAC, "00:1e:42:00:00:02"),
    }


# --- SMS --------------------------------------------------------------------


async def test_sms_sensor_counts_the_inbox(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "sensor", "sms_messages")).state == "2"


async def test_sms_sensor_lists_the_newest_messages_first(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    state = hass.states.get(entity_id(hass, "sensor", "sms_messages"))
    assert state.attributes["messages"] == [
        {
            "sender": "Provider",
            "date": "2026-11-18 08:30:00",
            "status": "unread",
            "message": "Welcome",
        },
        {
            "sender": "+491701111111",
            "date": "2026-11-17 10:00:00",
            "status": "read",
            "message": "Data volume used up",
        },
    ]


def test_inbox_is_cut_to_the_newest_and_the_texts_stay_out_of_the_recorder() -> None:
    from custom_components.teltonika_control.models import SmsMessage, newest_sms
    from custom_components.teltonika_control.sensor import TeltonikaSmsSensor

    many = [
        SmsMessage(f"k{i}", str(i), "m", "s", None, f"2026-11-18 10:{i:02d}:00", f"t{i}")
        for i in range(15)
    ]
    newest = newest_sms(many, 10)
    assert [m.message_id for m in newest] == [str(i) for i in range(14, 4, -1)]
    assert "messages" in TeltonikaSmsSensor._unrecorded_attributes

async def test_router_without_sms_page_has_no_sms_sensor(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, sms=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_sms_messages") is None


async def test_a_new_sms_fires_an_event_but_old_ones_do_not(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    events = async_capture_events(hass, EVENT_SMS_RECEIVED)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    # The messages that were already there at startup are not announced.
    assert events == []

    fresh = {
        "id": "3",
        "modem_id": "2-1.1",
        "sender": "+491702222222",
        "status": "unread",
        "date": "2026-11-18 09:00:00",
        "message": "Open the gate",
    }

    async def inbox() -> list[dict[str, Any]]:
        return SMS_MESSAGES + [fresh]

    monkeypatch.setattr(coordinator.client, "async_sms_messages", inbox)
    coordinator._invalidate_config_pages()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        "router": SERIAL,
        "sender": "+491702222222",
        "message": "Open the gate",
        "date": "2026-11-18 09:00:00",
        "modem": "2-1.1",
        "status": "unread",
    }
    assert hass.states.get(entity_id(hass, "sensor", "sms_messages")).state == "3"

    # The same inbox again announces nothing.
    coordinator._invalidate_config_pages()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_send_sms_returns_the_parts_used_and_keeps_text_out_of_the_log(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    caplog.set_level(logging.DEBUG, logger="custom_components.teltonika_control")

    result = await hass.services.async_call(
        DOMAIN,
        "send_sms",
        {
            "entity_id": entity_id(hass, "sensor", "uplink"),
            "number": "+49 170 1234567",
            "message": "Secret gate code 4711",
        },
        blocking=True,
        return_response=True,
    )

    assert result == {"sms_used": 2}
    assert requests(aioclient_mock, "POST", "/messages/actions/send")[0][2] == {
        "data": {
            "modem": "2-1.1",
            "number": "+491701234567",
            "message": "Secret gate code 4711",
        }
    }
    assert "4711" not in caplog.text
    assert "1234567" not in caplog.text


async def test_send_sms_needs_a_valid_number_and_a_clear_modem(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    target = entity_id(hass, "sensor", "uplink")

    for bad in ("hello", "12", "+49 170 abc"):
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                "send_sms",
                {"entity_id": target, "number": bad, "message": "x"},
                blocking=True,
            )
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "send_sms",
            {"entity_id": target, "number": "+491701234567", "message": ""},
            blocking=True,
        )

    # With two modems the caller has to say which one; naming it works.
    monkeypatch.setattr(entry.runtime_data, "modem_ids", lambda: ["a", "b"])
    with pytest.raises(HomeAssistantError, match="Choose the modem"):
        await hass.services.async_call(
            DOMAIN,
            "send_sms",
            {"entity_id": target, "number": "+491701234567", "message": "x"},
            blocking=True,
        )
    assert not requests(aioclient_mock, "POST", "/messages/actions/send")


# --- firmware ---------------------------------------------------------------


async def test_firmware_update_entity_shows_a_newer_stable_release(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    state = hass.states.get(entity_id(hass, "update", "firmware"))
    assert state.state == "on"
    assert state.attributes["installed_version"] == "RUTC_R_00.07.26.2"
    assert state.attributes["latest_version"] == "RUTC_R_00.07.27.1"
    assert state.attributes["newest_release"] == "RUTC_R_00.07.28.1"
    # It only informs: the router installs firmware itself.
    assert state.attributes["supported_features"] == 0


async def test_firmware_update_entity_is_off_when_up_to_date(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(
        aioclient_mock,
        firmware={"device": {"stable_version": "RUTC_R_00.07.26.2"}},
    )
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "update", "firmware")).state == "off"


async def test_firmware_placeholder_stable_version_falls_back_to_the_newest(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(
        aioclient_mock,
        firmware={"device": {"version": "RUTC_R_00.07.26.2", "stable_version": "newest"}},
    )
    await setup_entry(hass, entry)

    state = hass.states.get(entity_id(hass, "update", "firmware"))
    assert state.state == "off"
    assert state.attributes["latest_version"] == "RUTC_R_00.07.26.2"

async def test_router_without_firmware_information_has_no_update_entity(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, firmware=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("update", DOMAIN, f"{SERIAL}_firmware") is None


# --- discovery --------------------------------------------------------------


def discovery(ip: str = HOST) -> DhcpServiceInfo:
    return DhcpServiceInfo(ip=ip, hostname="teltonika", macaddress="001e42000001")


async def start_dhcp(hass: HomeAssistant, ip: str = HOST) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=discovery(ip)
    )


def known_router(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """A configured router that is not running, with its MAC in the registry."""
    entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, SERIAL)},
        connections={(CONNECTION_NETWORK_MAC, ROUTER_MAC)},
    )


def mock_other_address(aioclient_mock: Any, serial: str = SERIAL) -> None:
    """A router answering on another address."""
    status = {**DEVICE_STATUS, "mnfinfo": {**DEVICE_STATUS["mnfinfo"], "serial": serial}}
    aioclient_mock.post(
        f"https://{NEW_HOST}/api/login",
        json={"success": True, "data": {"token": "tok", "expires": 299}},
    )
    aioclient_mock.get(
        f"https://{NEW_HOST}/api/system/device/status",
        json={"success": True, "data": status},
    )


async def test_discovered_router_is_added_with_its_login(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)

    result = await start_dhcp(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["data"][CONF_HOST] == HOST


async def test_discovered_router_with_a_wrong_login_asks_again(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_login_failure(aioclient_mock)

    result = await start_dhcp(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_known_router_is_not_offered_again(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    known_router(hass, entry)

    result = await start_dhcp(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == ENTRY_DATA[CONF_HOST]


async def test_known_router_keeps_an_address_that_still_answers(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    # The router is also seen on a WAN address; the working LAN one stays.
    mock_router(aioclient_mock)
    mock_other_address(aioclient_mock)
    known_router(hass, entry)

    result = await start_dhcp(hass, NEW_HOST)

    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


async def test_known_router_follows_a_new_address_when_the_old_one_is_silent(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_unreachable(aioclient_mock)
    mock_other_address(aioclient_mock)
    known_router(hass, entry)

    result = await start_dhcp(hass, NEW_HOST)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == NEW_HOST


async def test_known_router_ignores_another_router_on_the_new_address(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_unreachable(aioclient_mock)
    mock_other_address(aioclient_mock, serial="9999999999")
    known_router(hass, entry)

    result = await start_dhcp(hass, NEW_HOST)

    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


# --- HTTPS first, then plain HTTP -------------------------------------------


def mock_plain_http(aioclient_mock: Any, *, login_ok: bool = True) -> None:
    """A router that only serves plain HTTP."""
    base = f"http://{HOST}/api"
    if login_ok:
        aioclient_mock.post(
            f"{base}/login",
            json={"success": True, "data": {"token": "tok", "expires": 299}},
        )
        aioclient_mock.get(
            f"{base}/system/device/status",
            json={"success": True, "data": DEVICE_STATUS},
        )
    else:
        aioclient_mock.post(
            f"{base}/login",
            status=401,
            json={"success": False, "errors": [{"code": 120, "error": "Invalid"}]},
        )


async def test_setup_falls_back_to_plain_http(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_unreachable(aioclient_mock)
    mock_plain_http(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("custom_components.teltonika_control.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ENTRY_DATA
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == f"http://{HOST}"


async def test_https_that_answers_is_kept(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("custom_components.teltonika_control.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ENTRY_DATA
        )

    assert result["data"][CONF_HOST] == HOST
    plain_logins = [
        c for c in aioclient_mock.mock_calls if str(c[1]).startswith("http://")
    ]
    assert not plain_logins


async def test_an_explicit_scheme_is_not_retried(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_unreachable(aioclient_mock)
    mock_plain_http(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ENTRY_DATA, CONF_HOST: f"https://{HOST}"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_plain_http_with_a_wrong_login_says_so(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_unreachable(aioclient_mock)
    mock_plain_http(aioclient_mock, login_ok=False)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)

    assert result["errors"] == {"base": "invalid_auth"}
