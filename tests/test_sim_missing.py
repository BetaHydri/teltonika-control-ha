"""An empty SIM slot is detected and a switch to it is undone."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.api import TeltonikaClient
from custom_components.teltonika_control.models import modem_sim_missing

from .conftest import entity_id, mock_router
from .payloads import MODEMS
from .test_integration import setup_entry


@pytest.mark.parametrize(
    ("simstate", "missing"),
    [
        ("Not inserted", True),
        ("not inserted", True),
        ("Inserted", False),
        ("Ready", False),
        (None, None),
        ("", None),
    ],
)
def test_sim_state_is_read_as_missing(simstate: str | None, missing: bool | None) -> None:
    assert modem_sim_missing({"simstate": simstate}) is missing


@pytest.fixture
def router_sim(monkeypatch: pytest.MonkeyPatch):
    """A modem whose slot 2 is empty; switching flips the active slot."""

    def install(
        coordinator: Any, empty_slots: set[int], stale: dict[str, bool] | None = None
    ) -> list[int]:
        state = {"active": 1}
        switches: list[int] = []

        async def answer() -> list[dict[str, Any]]:
            modem = deepcopy(MODEMS[0])
            modem["active_sim"] = state["active"]
            empty = state["active"] in empty_slots or bool(stale and stale["on"])
            modem["simstate"] = "Not inserted" if empty else "Inserted"
            return [modem]

        async def switch(modem_id: str) -> None:
            state["active"] = 2 if state["active"] == 1 else 1
            switches.append(state["active"])

        monkeypatch.setattr(coordinator.client, "async_modems_status", answer)
        monkeypatch.setattr(coordinator.client, "async_switch_sim", switch)
        return switches

    return install


async def test_the_sensor_shows_an_empty_slot(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    router_sim: Any,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    sensor = entity_id(hass, "binary_sensor", "2-1.1_sim_missing")
    assert hass.states.get(sensor).state == STATE_OFF

    coordinator = entry.runtime_data
    router_sim(coordinator, {1})
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == STATE_ON


async def test_switching_to_an_empty_slot_goes_back(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    router_sim: Any,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    switches = router_sim(entry.runtime_data, {2})

    with pytest.raises(HomeAssistantError, match="no SIM in slot 2.*back to SIM 1"):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id(hass, "select", "2-1.1_sim"), "option": "sim_2"},
            blocking=True,
        )

    assert switches == [2, 1]
    assert hass.states.get(entity_id(hass, "select", "2-1.1_sim")).state == "sim_1"
    assert (
        hass.states.get(entity_id(hass, "binary_sensor", "2-1.1_sim_missing")).state
        == STATE_OFF
    )


async def test_with_both_slots_empty_there_is_no_back_and_forth(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    router_sim: Any,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    switches = router_sim(coordinator, {1, 2})
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", "2-1.1_sim"), "option": "sim_2"},
        blocking=True,
    )

    assert switches == [2]
    assert hass.states.get(entity_id(hass, "select", "2-1.1_sim")).state == "sim_2"


async def test_a_single_slot_modem_has_no_select_but_shows_a_missing_sim(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def answer(self: Any) -> list[dict[str, Any]]:
        modem = deepcopy(MODEMS[0])
        modem["sim_count"] = 1
        modem["simstate"] = "Not inserted"
        return [modem]

    monkeypatch.setattr(TeltonikaClient, "async_modems_status", answer)
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    assert not [
        e
        for e in er.async_get(hass).entities.values()
        if e.unique_id.endswith("_sim") and e.domain == "select"
    ]
    sensor = entity_id(hass, "binary_sensor", "2-1.1_sim_missing")
    assert hass.states.get(sensor).state == STATE_ON

    with pytest.raises(HomeAssistantError, match="only one SIM slot"):
        await entry.runtime_data.async_switch_sim("2-1.1", 2)


async def test_a_stale_reading_after_a_switch_back_does_not_block_the_next_try(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    router_sim: Any,
) -> None:
    """Right after a switch the old slot may still be reported as not inserted."""
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    stale = {"on": False}
    switches = router_sim(entry.runtime_data, {2}, stale)
    select = entity_id(hass, "select", "2-1.1_sim")

    for _ in range(2):
        with pytest.raises(HomeAssistantError, match="no SIM in slot 2"):
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": select, "option": "sim_2"},
                blocking=True,
            )
        stale["on"] = True

    assert switches == [2, 1, 2, 1]


async def test_switching_to_a_slot_with_a_sim_stays(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    router_sim: Any,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    switches = router_sim(entry.runtime_data, set())

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", "2-1.1_sim"), "option": "sim_2"},
        blocking=True,
    )

    assert switches == [2]
    assert hass.states.get(entity_id(hass, "select", "2-1.1_sim")).state == "sim_2"
