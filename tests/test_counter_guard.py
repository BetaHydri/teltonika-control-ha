"""A modem counter that is read as 0 for one poll must not look like a reset."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.models import (
    COUNTER_RESET_POLLS,
    guard_counter,
)

from .conftest import entity_id, mock_router
from .payloads import MODEMS
from .test_integration import setup_entry


def test_a_single_zero_is_held() -> None:
    assert guard_counter(1000.0, 0.0, 0) == (1000.0, 1)


def test_a_small_fall_is_taken_over() -> None:
    # Home Assistant ignores a fall of less than 10 percent as well.
    assert guard_counter(1000.0, 950.0, 0) == (950.0, 0)


def test_a_normal_rise_resets_the_count() -> None:
    assert guard_counter(1000.0, 1010.0, 2) == (1010.0, 0)


def test_a_real_reset_is_accepted_after_a_few_readings() -> None:
    value, pending = 1000.0, 0
    for _ in range(COUNTER_RESET_POLLS - 1):
        value, pending = guard_counter(1000.0, 5.0, pending)
        assert value == 1000.0
    value, pending = guard_counter(1000.0, 5.0, pending)
    assert (value, pending) == (5.0, 0)


@pytest.mark.parametrize(("last", "new"), [(None, 0.0), (1000.0, None), (None, None)])
def test_nothing_to_compare_passes_the_value_on(last: float | None, new: float | None) -> None:
    assert guard_counter(last, new, 0) == (new, 0)


async def poll(hass: HomeAssistant, entry: MockConfigEntry, monkeypatch: Any, rx: Any) -> None:
    coordinator = entry.runtime_data
    modems = deepcopy(MODEMS)
    modems[0]["rxbytes"] = rx

    async def answer() -> list[dict[str, Any]]:
        return modems

    monkeypatch.setattr(coordinator.client, "async_modems_status", answer)
    await coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_the_received_sensor_ignores_a_single_zero_reading(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    registry = er.async_get(hass)
    registry.async_update_entity(entity_id(hass, "sensor", "2-1.1_received"), disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    sensor = entity_id(hass, "sensor", "2-1.1_received")
    before = float(hass.states.get(sensor).state)
    assert before > 0

    await poll(hass, entry, monkeypatch, 0)
    assert float(hass.states.get(sensor).state) == before

    await poll(hass, entry, monkeypatch, 2 * 1048576)
    assert float(hass.states.get(sensor).state) == 2.097152
