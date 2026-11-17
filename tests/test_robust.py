"""The uplink follows the failover, and GPS keeps its last known position."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.models import (
    FailoverInterface,
    TeltonikaData,
    Uplink,
    WifiClient,
    derive_failover,
    derive_portal_state,
    derive_uplink,
)

from .conftest import entity_id, mock_router
from .payloads import GPS_STATUS
from .test_gps_glitch import poll, reading
from .test_integration import setup_entry

MOBILE = {
    "id": "mob1s1a1",
    "name": "mob1s1a1",
    "metric": 4,
    "route": [{"target": "0.0.0.0", "mask": 0}],
}
WIFI = {
    "id": "wan2",
    "name": "wifi4",
    "metric": 1,
    "route": [{"target": "0.0.0.0", "mask": 0}],
}


def test_uplink_passes_over_an_interface_the_failover_calls_offline() -> None:
    uplink = derive_uplink([MOBILE, WIFI], {"wifi4"}, {"wifi4"})
    assert uplink is not None
    assert uplink.kind == "mobile"
    assert uplink.skipped == "wifi4"


def test_uplink_keeps_the_best_metric_when_all_are_offline() -> None:
    uplink = derive_uplink([MOBILE, WIFI], {"wifi4"}, {"wifi4", "mob1s1a1"})
    assert uplink is not None
    assert uplink.kind == "wifi"
    assert uplink.skipped is None


def test_uplink_without_failover_data_follows_the_metric() -> None:
    uplink = derive_uplink([MOBILE, WIFI], {"wifi4"})
    assert uplink is not None
    assert uplink.kind == "wifi"
    assert uplink.skipped is None


def test_expired_hotspot_login_is_seen_although_mobile_carries_the_traffic() -> None:
    wifi = WifiClient("cfg", "ArtSpot", "wifi4", -50, 72, "2.4 GHz", 11)
    mobile = Uplink("mob1s1a1", "mob1s1a1", "mobile", "10.1.2.3", 4)
    kwargs = {"waiting": False, "wifi_client": wifi, "uplink": mobile, "internet": True}
    assert derive_portal_state(**kwargs, wifi_failed=True) == "login_required"
    assert derive_portal_state(**kwargs, wifi_failed=False) == "idle"
    # Without a connected Wi-Fi there is nothing to log in to.
    kwargs["wifi_client"] = None
    assert derive_portal_state(**kwargs, wifi_failed=True) == "no_wifi"


def test_wifi_failed_needs_a_wifi_interface_and_none_online() -> None:
    def row(kind: str, online: bool | None) -> FailoverInterface:
        return FailoverInterface("id", "x", kind, None, online, None, None, None, None, None)

    assert TeltonikaData(failover=[]).wifi_failed is False
    assert TeltonikaData(failover=[row("mobile", False)]).wifi_failed is False
    assert TeltonikaData(failover=[row("wifi", False), row("wifi", False)]).wifi_failed
    assert not TeltonikaData(failover=[row("wifi", False), row("wifi", True)]).wifi_failed
    assert not TeltonikaData(failover=[row("wifi", None)]).wifi_failed


def test_standby_counts_as_online_and_offline_as_offline() -> None:
    raw = {
        "mob1s1a1": {"enabled": True, "status": "standby"},
        "wan2": {"enabled": True, "status": "offline"},
        "wan3": {"enabled": True, "status": "starting"},
    }
    online = {i.interface_id: i.online for i in derive_failover(raw)}
    assert online == {"mob1s1a1": True, "wan2": False, "wan3": None}


async def test_gps_keeps_the_last_position_when_the_fix_is_lost(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    data = await poll(coordinator, monkeypatch, reading(7))
    assert data.gps_fix is True
    assert data.gps_position.latitude == pytest.approx(48.436849)

    lost = {"latitude": "0", "longitude": "0", "satellites": "0", "accuracy": "500"}
    for _ in range(10):
        data = await poll(coordinator, monkeypatch, lost)

    assert data.gps is None
    assert data.gps_fix is False
    assert data.gps_satellites == 0
    assert data.gps_position.latitude == pytest.approx(48.436849)
    assert data.gps_last_fix is not None


async def test_gps_entities_show_the_last_position_without_a_fix(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    await poll(coordinator, monkeypatch, reading(7))

    lost = {"latitude": "0", "longitude": "0", "satellites": "0", "accuracy": "500"}
    for _ in range(10):
        data = await poll(coordinator, monkeypatch, lost)
    coordinator.async_set_updated_data(data)
    await hass.async_block_till_done()

    tracker = hass.states.get(entity_id(hass, "device_tracker", "gps"))
    assert tracker.attributes["latitude"] == pytest.approx(48.436849)
    assert tracker.attributes["fix"] is False
    assert "last_fix" in tracker.attributes
    signal = hass.states.get(entity_id(hass, "binary_sensor", "gps_signal"))
    assert signal.state == "off"
    satellites = hass.states.get(entity_id(hass, "sensor", "gps_satellites"))
    assert float(satellites.state) == 0


async def test_gps_without_any_fix_since_the_start_has_no_position(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
) -> None:
    mock_router(
        aioclient_mock,
        gps={"latitude": "0", "longitude": "0", "satellites": "0", "speed": "0"},
    )
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "device_tracker", "gps")).state == "unknown"
    assert hass.states.get(entity_id(hass, "binary_sensor", "gps_signal")).state == "off"
    assert float(hass.states.get(entity_id(hass, "sensor", "gps_satellites")).state) == 0


async def test_gps_position_survives_a_restart(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    hass_storage[f"teltonika_control.{entry.entry_id}.gps"] = {
        "version": 1,
        "key": f"teltonika_control.{entry.entry_id}.gps",
        "data": {
            "latitude": 52.5,
            "longitude": 13.4,
            "altitude": 34.0,
            "accuracy": 1.5,
            "satellites": 8,
            "at": "2026-11-17T10:00:00+00:00",
        },
    }
    mock_router(
        aioclient_mock,
        gps={**GPS_STATUS, "latitude": "0", "longitude": "0", "satellites": "0"},
    )
    await setup_entry(hass, entry)

    tracker = hass.states.get(entity_id(hass, "device_tracker", "gps"))
    assert tracker.attributes["latitude"] == pytest.approx(52.5)
    assert tracker.attributes["last_fix"].startswith("2026-11-17T10:00:00")
    assert tracker.attributes["fix"] is False
