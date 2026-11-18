"""Fixtures for Teltonika Control tests."""

from __future__ import annotations

import itertools
from typing import Any

import aiohttp
import pytest
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import DOMAIN, VPN_FAMILIES

from .payloads import BASE, DEVICE_STATUS, HOST, PROBE_URL, SERIAL, payloads

ENTRY_DATA = {
    CONF_HOST: HOST,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
    CONF_VERIFY_SSL: False,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from this repository."""


@pytest.fixture(autouse=True)
def no_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the waiting built into actions and portal mode."""
    for name in (
        "AP_REFRESH_DELAY",
        "ROAMING_REFRESH_DELAY",
        "PORT_FORWARD_REFRESH_DELAY",
        "VPN_RECONNECT_DELAY",
        "VPN_REFRESH_DELAY",
        "PORTAL_FIRST_DELAY",
        "PORTAL_POLL_INTERVAL",
        "PRIORITY_VERIFY_DELAY",
    ):
        monkeypatch.setattr(f"custom_components.teltonika_control.coordinator.{name}", 0)

    # Each reading of the portal deadline clock jumps 30 s, so a one minute
    # wait ends after a few polls instead of after a real minute.
    clock = itertools.count(0, 30)
    monkeypatch.setattr(
        "custom_components.teltonika_control.coordinator._monotonic",
        lambda: float(next(clock)),
    )


def forbidden(aioclient_mock: Any, path: str) -> None:
    """The router user may not read this page."""
    aioclient_mock.get(
        f"{BASE}{path}",
        status=403,
        json={"success": False, "errors": [{"code": 403, "error": "Forbidden"}]},
    )


def mock_router(
    aioclient_mock: Any,
    *,
    wifi_metric: int | None = None,
    internet: bool = True,
    gps: dict[str, Any] | bool = True,
    date: str | None = None,
    usage: bool = True,
    dhcp: bool = True,
    wireguard: bool = True,
    sim_cards: bool = True,
    port_forwards: bool = True,
    traffic_rules: bool = True,
    failover: bool = True,
    data_limit: bool = True,
    sms: bool = True,
    firmware: dict[str, Any] | bool = True,
    vpn: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Register answers for every endpoint the integration polls.

    ``gps`` is True for the default position, a dict for a custom answer and
    False for a router without GPS (the endpoint is missing). ``usage``,
    ``dhcp``, ``wireguard`` and the other page switches False simulate a user
    without the right to read that page. ``vpn`` maps a VPN type such as
    "tailscale" to its ``config`` and ``status`` answers; the other types
    are missing on the router.
    """
    data = payloads(wifi_metric=wifi_metric, wireguard=wireguard)
    headers = {"Date": date} if date else None
    aioclient_mock.post(
        f"{BASE}/login",
        json={"success": True, "data": {"token": "tok", "expires": 299}},
    )
    for enabled, path, body in (
        (usage, "/system/device/usage/status", data["usage"]),
        (dhcp, "/dhcp/leases/ipv4/status", data["dhcp"]),
        (wireguard, "/wireguard/config", data["wireguard"]),
        (sim_cards, "/sim_cards/config", data["sim_cards"]),
        (port_forwards, "/firewall/port_forwards/config", data["port_forwards"]),
        (traffic_rules, "/firewall/traffic_rules/config", data["traffic_rules"]),
        (failover, "/failover/status", data["failover"]),
        (failover, "/failover/interfaces/config", data["failover_config"]),
        (data_limit, "/data_limit/status", data["data_limit"]),
        (sms, "/messages/status", data["sms"]),
        (
            firmware is not False,
            "/firmware/device/updates/status",
            firmware if isinstance(firmware, dict) else data["firmware_updates"],
        ),
    ):
        if enabled:
            aioclient_mock.get(f"{BASE}{path}", json={"success": True, "data": body})
        else:
            forbidden(aioclient_mock, path)
    for kind in VPN_FAMILIES:
        answers = (vpn or {}).get(kind.key)
        for page, path in (("config", kind.config_path), ("status", kind.status_path)):
            if answers is None or page not in answers:
                aioclient_mock.get(
                    f"{BASE}{path}",
                    status=404,
                    json={"success": False, "errors": [{"code": 404, "error": "Not found"}]},
                )
                continue
            aioclient_mock.get(f"{BASE}{path}", json={"success": True, "data": answers[page]})
        for item in (answers or {}).get("config", []):
            for method in (aioclient_mock.post, aioclient_mock.put, aioclient_mock.delete):
                method(f"{BASE}{kind.config_path}/{item['id']}", json={"success": True})
    if gps is False:
        aioclient_mock.get(
            f"{BASE}/gps/position/status",
            status=404,
            json={"success": False, "errors": [{"code": 404, "error": "Not found"}]},
        )
    else:
        aioclient_mock.get(
            f"{BASE}/gps/position/status",
            json={"success": True, "data": data["gps"] if gps is True else gps},
        )
    for path, body in (
        ("/system/device/status", DEVICE_STATUS),
        ("/interfaces/status", data["interfaces"]),
        ("/interfaces/config", data["config"]),
        ("/wireless/interfaces/config", data["wireless_config"]),
        ("/wireless/interfaces/status", data["wireless_status"]),
        ("/wireless/devices/status", data["wireless_devices"]),
        ("/modems/status", data["modems"]),
    ):
        aioclient_mock.get(
            f"{BASE}{path}",
            json={"success": True, "data": body},
            headers=headers,
        )
    aioclient_mock.get(PROBE_URL, status=204 if internet else 200)
    for method in (aioclient_mock.post, aioclient_mock.put, aioclient_mock.delete):
        method(f"{BASE}/system/actions/reboot", json={"success": True})
        method(f"{BASE}/modems/2-1.1/actions/restart_connection", json={"success": True})
        method(f"{BASE}/modems/2-1.1/actions/switch_sim", json={"success": True})
        method(f"{BASE}/wireless/actions/reconnect", json={"success": True})
        method(f"{BASE}/interfaces/config/wan2", json={"success": True})
        method(f"{BASE}/wireless/interfaces/config/default_radio1", json={"success": True})
        method(f"{BASE}/wireless/interfaces/config/6", json={"success": True})
        method(f"{BASE}/wireguard/config/HOMEBASE", json={"success": True})
        method(f"{BASE}/sim_cards/config/cfg_sim1", json={"success": True})
        method(f"{BASE}/sim_cards/config/cfg_sim2", json={"success": True})
        method(f"{BASE}/firewall/port_forwards/config/cfg_ssh", json={"success": True})
        method(f"{BASE}/firewall/port_forwards/config/cfg_web", json={"success": True})
        method(f"{BASE}/firewall/traffic_rules/config/15", json={"success": True})
        method(f"{BASE}/firewall/traffic_rules/config/21", json={"success": True})
        method(
            f"{BASE}/messages/actions/send",
            json={"success": True, "data": {"sms_used": 2}},
        )


def mock_login_failure(aioclient_mock: Any) -> None:
    """The router rejects the credentials."""
    aioclient_mock.post(
        f"{BASE}/login",
        status=401,
        json={"success": False, "errors": [{"code": 120, "error": "Invalid credentials"}]},
    )


def mock_unreachable(aioclient_mock: Any) -> None:
    """The router does not answer."""
    aioclient_mock.post(f"{BASE}/login", exc=aiohttp.ClientError("unreachable"))


@pytest.fixture
def entry() -> MockConfigEntry:
    """Return a config entry for the sample router."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id=SERIAL,
        title="Teltonika-RUTC50.com",
    )


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    """Resolve an entity id by the unique id key used by the integration."""
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{SERIAL}_{key}")
    assert found is not None, f"no {platform} entity with key {key}"
    return found


def find_device(hass: HomeAssistant, identifier: tuple[str, str]) -> dr.DeviceEntry:
    """Look up a device by identifier on old and new Home Assistant versions."""
    registry = dr.async_get(hass)
    if hasattr(registry, "async_get_devices"):
        devices = registry.async_get_devices(identifiers={identifier})
        assert len(devices) == 1
        return devices[0]
    device = registry.async_get_device(identifiers={identifier})
    assert device is not None
    return device


def router_device_id(hass: HomeAssistant) -> str:
    """Return the device registry id of the router."""
    return find_device(hass, (DOMAIN, SERIAL)).id
