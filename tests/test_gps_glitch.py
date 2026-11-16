"""GPS readings with 0 satellites between normal ones are ignored."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import GPS_GLITCH_POLLS

from .conftest import mock_router
from .payloads import GPS_STATUS
from .test_integration import setup_entry


def reading(satellites: int, accuracy: str = "0.6") -> dict[str, Any]:
    return {**GPS_STATUS, "satellites": str(satellites), "accuracy": accuracy}


async def poll(coordinator: Any, monkeypatch: pytest.MonkeyPatch, raw: dict[str, Any]):
    async def answer() -> dict[str, Any]:
        return raw

    monkeypatch.setattr(coordinator.client, "async_gps_status", answer)
    return await coordinator._async_update_data()


async def test_single_empty_readings_are_ignored(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    data = await poll(coordinator, monkeypatch, reading(7))
    assert data.gps.satellites == 7

    data = await poll(coordinator, monkeypatch, reading(0, "500"))
    assert data.gps.satellites == 7
    assert data.gps.accuracy == 0.6

    data = await poll(coordinator, monkeypatch, reading(6))
    assert data.gps.satellites == 6


async def test_a_real_loss_of_the_fix_shows_up(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    await poll(coordinator, monkeypatch, reading(7))

    for _ in range(GPS_GLITCH_POLLS):
        data = await poll(coordinator, monkeypatch, reading(0, "500"))
        assert data.gps.satellites == 7

    data = await poll(coordinator, monkeypatch, reading(0, "500"))
    assert data.gps.satellites == 0
    assert data.gps.accuracy == 500

    # Still empty: stays empty instead of flipping back to the old fix.
    data = await poll(coordinator, monkeypatch, reading(0, "500"))
    assert data.gps.satellites == 0
