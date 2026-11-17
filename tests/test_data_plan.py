"""The data plan option: the data limit is measured against the contract."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import (
    CONF_DATA_PLAN,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)
from custom_components.teltonika_control.models import derive_data_limits

from .conftest import ENTRY_DATA, entity_id, mock_router
from .payloads import DATA_LIMIT_STATUS, INTERFACES_CONFIG, SERIAL
from .test_integration import setup_entry

PLAN_BYTES = 8_000_000_000


def test_without_a_plan_the_router_limit_counts() -> None:
    (limit,) = derive_data_limits(DATA_LIMIT_STATUS, INTERFACES_CONFIG)
    assert limit.limit == 10_000_000_000
    assert limit.used_percent == 20.0


def test_a_plan_replaces_the_router_limit() -> None:
    (limit,) = derive_data_limits(DATA_LIMIT_STATUS, INTERFACES_CONFIG, PLAN_BYTES)
    assert limit.limit == PLAN_BYTES
    assert limit.used == 2_000_000_000
    assert limit.used_percent == 25.0
    assert limit.reached is False


def test_the_plan_can_be_used_up_below_the_router_limit() -> None:
    raw = [{**DATA_LIMIT_STATUS[0], "data_used": "8500000000"}]
    (limit,) = derive_data_limits(raw, INTERFACES_CONFIG, PLAN_BYTES)
    assert limit.reached is True
    assert limit.used_percent == 106.2
    # The router's own limit (10 GB) is not reached yet.
    (router,) = derive_data_limits(raw, INTERFACES_CONFIG)
    assert router.reached is False


@pytest.mark.parametrize("plan", [None, 0, 0.0, -5])
def test_no_or_invalid_plan_uses_the_router_limit(plan: float | None) -> None:
    (limit,) = derive_data_limits(DATA_LIMIT_STATUS, INTERFACES_CONFIG, plan)
    assert limit.limit == 10_000_000_000


def test_a_plan_does_not_create_a_limit_the_router_does_not_have() -> None:
    raw = [{"interface": "mob1s1a1", "enabled": "0"}]
    assert derive_data_limits(raw, INTERFACES_CONFIG, PLAN_BYTES) == []


async def test_the_option_changes_percent_and_reached(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id=SERIAL,
        options={CONF_DATA_PLAN: 4},
    )
    await setup_entry(hass, entry)

    # 2 GB of a 4 GB plan, not of the router's 10 GB.
    percent = hass.states.get(entity_id(hass, "sensor", "data_limit_mob1s1a1_percent"))
    assert float(percent.state) == pytest.approx(50.0)
    limit = hass.states.get(entity_id(hass, "sensor", "data_limit_mob1s1a1_limit"))
    assert float(limit.state) == pytest.approx(4.0)


async def test_options_flow_stores_the_plan(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30, CONF_DATA_PLAN: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DATA_PLAN] == 60


async def test_an_emptied_plan_is_stored_as_none(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id=SERIAL,
        options={CONF_DATA_PLAN: 60},
    )
    await setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DATA_PLAN] == 0
    assert entry.runtime_data._data_plan_bytes == 0
