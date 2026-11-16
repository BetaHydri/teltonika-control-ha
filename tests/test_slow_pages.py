"""A router page that does not answer must not take the whole router offline."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.api import TeltonikaConnectionError

from .conftest import BASE, entity_id, mock_router
from .test_integration import setup_entry


async def test_setup_works_while_the_wireless_status_hangs(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    aioclient_mock.get(f"{BASE}/wireless/interfaces/status", exc=TimeoutError())
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "sensor", "uplink")).state == "mobile"
    assert hass.states.get(entity_id(hass, "binary_sensor", "internet")).state == "on"
    assert hass.states.get(entity_id(hass, "sensor", "2-1.1_operator")).state == "Testnet"


async def test_wifi_name_and_state_survive_a_hanging_wireless_status(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    aioclient_mock.get(f"{BASE}/wireless/interfaces/status", exc=TimeoutError())
    mock_router(aioclient_mock, wifi_metric=0)
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "sensor", "uplink")).state == "wifi"
    assert hass.states.get(entity_id(hass, "sensor", "wifi_ssid")).state == "CampWifi"
    assert hass.states.get(entity_id(hass, "sensor", "wifi_band")).state == "2.4 GHz"
    assert hass.states.get(entity_id(hass, "binary_sensor", "wifi_connected")).state == (
        "on"
    )
    assert hass.states.get(entity_id(hass, "sensor", "portal_state")).state == "online"


async def test_last_known_values_are_kept_and_the_page_is_left_alone(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    signal = entity_id(hass, "sensor", "wifi_signal")
    assert float(hass.states.get(signal).state) == -61

    calls = 0
    original = coordinator.client.async_wireless_status
    async def hanging() -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        raise TeltonikaConnectionError("timeout")

    monkeypatch.setattr(coordinator.client, "async_wireless_status", hanging)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert float(hass.states.get(signal).state) == -61
    assert calls == 1

    # Within the pause the page is not asked again.
    await coordinator.async_refresh()
    assert calls == 1

    # After the pause it is asked again, and a recovered page updates the data.
    coordinator._slow_until.clear()
    monkeypatch.setattr(coordinator.client, "async_wireless_status", original)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert "wireless_status" not in coordinator._slow_until
    assert float(hass.states.get(signal).state) == -61


async def test_essential_pages_still_fail_the_update(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def hanging() -> list[dict[str, Any]]:
        raise TeltonikaConnectionError("timeout")

    monkeypatch.setattr(coordinator.client, "async_interfaces_status", hanging)
    await coordinator.async_refresh()

    assert not coordinator.last_update_success
