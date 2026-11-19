"""The mobile data used today and this month."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.models import derive_data_usage

from .conftest import entity_id, mock_router
from .payloads import SERIAL
from .test_integration import setup_entry


def test_rows_are_summed_up() -> None:
    usage = derive_data_usage([[1, 100, 10], [2, "200", 20.5]])
    assert usage is not None
    assert (usage.received, usage.sent, usage.total) == (300, 30.5, 330.5)


def test_an_empty_day_is_zero_not_missing() -> None:
    usage = derive_data_usage([])
    assert usage is not None
    assert usage.total == 0


def test_a_wrapped_list_and_broken_rows_are_handled() -> None:
    usage = derive_data_usage({"usage": [[1, 5, 6], [2], "x", [3, None, 4]]})
    assert usage is not None
    assert (usage.received, usage.sent) == (5, 10)


@pytest.mark.parametrize("raw", [None, "nope", 5])
def test_a_missing_page_is_none(raw: Any) -> None:
    assert derive_data_usage(raw) is None


async def test_sensors_show_the_summed_traffic(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    today = hass.states.get(entity_id(hass, "sensor", "data_usage_today"))
    assert today is not None
    assert float(today.state) == pytest.approx(3.75)
    assert today.attributes["received_mb"] == 3.0
    assert today.attributes["sent_mb"] == 0.8

    month = hass.states.get(entity_id(hass, "sensor", "data_usage_month"))
    assert month is not None
    assert float(month.state) == pytest.approx(3.3)


async def test_router_without_the_pages_has_no_usage_sensors(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, data_usage=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    for key in ("data_usage_today", "data_usage_month"):
        assert registry.async_get_entity_id("sensor", "teltonika_control", f"{SERIAL}_{key}") is None
