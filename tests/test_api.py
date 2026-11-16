"""Tests for the RutOS API client."""

from __future__ import annotations

from typing import Any

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.teltonika_control.api import (
    TeltonikaApiError,
    TeltonikaAuthError,
    TeltonikaClient,
    TeltonikaConnectionError,
    parse_host,
)

from .payloads import BASE, HOST

LOGIN_OK = {"success": True, "data": {"token": "tok", "expires": 299}}


def make_client(hass: HomeAssistant) -> TeltonikaClient:
    session = async_get_clientsession(hass, verify_ssl=False)
    return TeltonikaClient(session, HOST, "admin", "secret")


def calls(aioclient_mock: Any, method: str, suffix: str) -> list[Any]:
    return [
        call
        for call in aioclient_mock.mock_calls
        if call[0] == method and str(call[1]).split("?")[0].endswith(suffix)
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.168.1.1", ("192.168.1.1", True)),
        (" https://router.lan/ ", ("router.lan", True)),
        ("http://10.0.0.1:8080/api", ("10.0.0.1:8080", False)),
        ("HTTP://10.0.0.1", ("10.0.0.1", False)),
    ],
)
def test_parse_host(value: str, expected: tuple[str, bool]) -> None:
    assert parse_host(value) == expected


async def test_token_is_sent_and_reused(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    aioclient_mock.post(f"{BASE}/login", json=LOGIN_OK)
    aioclient_mock.get(f"{BASE}/modems/status", json={"success": True, "data": []})
    client = make_client(hass)

    await client.async_modems_status()
    await client.async_modems_status()

    assert len(calls(aioclient_mock, "POST", "/login")) == 1
    modem_calls = calls(aioclient_mock, "GET", "/modems/status")
    assert len(modem_calls) == 2
    assert modem_calls[0][3]["Authorization"] == "Bearer tok"


async def test_rejected_token_triggers_one_relogin_then_auth_error(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    aioclient_mock.post(f"{BASE}/login", json=LOGIN_OK)
    aioclient_mock.get(
        f"{BASE}/modems/status",
        status=401,
        json={"success": False, "errors": [{"code": 120, "error": "Unauthorized"}]},
    )
    with pytest.raises(TeltonikaAuthError):
        await make_client(hass).async_modems_status()

    # Initial login plus exactly one retry after the token was rejected.
    assert len(calls(aioclient_mock, "POST", "/login")) == 2
    assert len(calls(aioclient_mock, "GET", "/modems/status")) == 2


async def test_wrong_password_raises_auth_error(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    aioclient_mock.post(
        f"{BASE}/login",
        status=401,
        json={"success": False, "errors": [{"code": 120, "error": "bad login"}]},
    )
    with pytest.raises(TeltonikaAuthError, match="bad login"):
        await make_client(hass).async_login()


async def test_unreachable_router_raises_connection_error(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    aioclient_mock.post(f"{BASE}/login", exc=aiohttp.ClientError("down"))
    with pytest.raises(TeltonikaConnectionError):
        await make_client(hass).async_login()


async def test_api_error_carries_router_message(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    aioclient_mock.post(f"{BASE}/login", json=LOGIN_OK)
    aioclient_mock.post(
        f"{BASE}/system/actions/reboot",
        status=422,
        json={"success": False, "errors": [{"code": 7, "error": "not now"}]},
    )
    with pytest.raises(TeltonikaApiError, match="not now") as err:
        await make_client(hass).async_reboot()
    assert err.value.status == 422
    assert err.value.code == 7


async def test_actions_use_documented_paths_and_bodies(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    aioclient_mock.post(f"{BASE}/login", json=LOGIN_OK)
    ok = {"success": True}
    for path in (
        "/modems/2-1.1/actions/restart_connection",
        "/wireless/actions/reconnect",
        "/wireless/actions/join",
    ):
        aioclient_mock.post(f"{BASE}{path}", json=ok)
    aioclient_mock.put(f"{BASE}/interfaces/config/wan2", json=ok)
    aioclient_mock.put(f"{BASE}/wireless/interfaces/config/default_radio1", json=ok)
    aioclient_mock.delete(f"{BASE}/wireless/interfaces/config/6", json=ok)
    aioclient_mock.post(f"{BASE}/wireless/multi_ap/config", json=ok)
    aioclient_mock.put(f"{BASE}/wireless/multi_ap/config/cfg1", json=ok)
    aioclient_mock.delete(f"{BASE}/wireless/multi_ap/config/cfg1", json=ok)
    aioclient_mock.delete(f"{BASE}/interfaces/config/wifi4", json=ok)
    client = make_client(hass)

    await client.async_restart_modem_connection("2-1.1")
    await client.async_reconnect_wifi("6")
    await client.async_set_interface_metric("wan2", "0")
    await client.async_set_wireless_enabled("default_radio1", True)
    await client.async_join_wifi(radio="radio0", ssid="Cafe", password="pw")
    await client.async_delete_wireless("6")
    await client.async_add_multi_ap(ssid="Camp5", password="pw12345678", priority=4)
    await client.async_update_multi_ap_key("cfg1", "newpass123")
    await client.async_delete_multi_ap("cfg1")
    await client.async_delete_interface("wifi4")

    def body(method: str, suffix: str) -> Any:
        return calls(aioclient_mock, method, suffix)[0][2]

    assert body("POST", "/wireless/actions/reconnect") == {"data": {"sta_id": "6"}}
    assert body("PUT", "/interfaces/config/wan2") == {"data": {"metric": "0"}}
    assert body("PUT", "/wireless/interfaces/config/default_radio1") == {
        "data": {"enabled": "1"}
    }
    assert body("POST", "/wireless/actions/join") == {
        "data": {"device": "radio0", "ssid": "Cafe", "password": "pw"}
    }
    assert len(calls(aioclient_mock, "DELETE", "/wireless/interfaces/config/6")) == 1
    assert body("POST", "/wireless/multi_ap/config") == {
        "data": {
            "ssid": "Camp5",
            "enabled": "1",
            "priority": "4",
            "key": "pw12345678",
        }
    }
    assert body("PUT", "/wireless/multi_ap/config/cfg1") == {"data": {"key": "newpass123"}}
    assert len(calls(aioclient_mock, "DELETE", "/wireless/multi_ap/config/cfg1")) == 1
    assert len(calls(aioclient_mock, "DELETE", "/interfaces/config/wifi4")) == 1
    join_call = calls(aioclient_mock, "POST", "/wireless/actions/join")[0]
    assert join_call[1].query["use_cache"] == "true"
