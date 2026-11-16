"""The data roaming switches of the SIM slots."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import DOMAIN
from custom_components.teltonika_control.models import derive_sim_cards

from .conftest import entity_id, mock_router
from .payloads import SERIAL, SIM_CARDS
from .test_integration import requests, setup_entry


def test_sim_cards_are_derived() -> None:
    cards = derive_sim_cards(SIM_CARDS)
    assert [(c.modem_id, c.slot, c.roaming_allowed) for c in cards] == [
        ("2-1.1", 1, True),
        ("2-1.1", 2, False),
    ]


def test_sim_cards_without_data() -> None:
    assert derive_sim_cards(None) == []
    assert derive_sim_cards([{"modem": "x"}]) == []
    (card,) = derive_sim_cards([{"id": "a", "modem": "x", "position": "1"}])
    assert card.roaming_allowed is None


async def test_roaming_switches_show_the_router_setting(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "switch", "2-1.1_roaming_sim1")).state == (
        STATE_ON
    )
    assert hass.states.get(entity_id(hass, "switch", "2-1.1_roaming_sim2")).state == (
        STATE_OFF
    )


@pytest.fixture
def router_state(monkeypatch: pytest.MonkeyPatch):
    """Let the router remember the roaming setting after a write."""
    state = {"cfg_sim1": "0", "cfg_sim2": "1"}
    writes: list[tuple[str, str]] = []

    def install(coordinator: Any, *, apply: bool = True) -> list[tuple[str, str]]:
        client = coordinator.client

        async def read() -> list[dict[str, Any]]:
            return [
                {**card, "deny_roaming": state[card["id"]]} for card in SIM_CARDS
            ]

        async def write(card_id: str, allowed: bool) -> None:
            value = "0" if allowed else "1"
            writes.append((card_id, value))
            if apply:
                state[card_id] = value

        monkeypatch.setattr(client, "async_sim_cards_config", read)
        monkeypatch.setattr(client, "async_set_sim_roaming", write)
        return writes

    return install


async def test_turning_roaming_on_and_off_writes_only_the_one_field(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    # The mocked router does not remember writes, so the read-back fails; the
    # request itself is what this test looks at.
    with pytest.raises(HomeAssistantError, match="did not apply"):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id(hass, "switch", "2-1.1_roaming_sim2")},
            blocking=True,
        )
    put = requests(aioclient_mock, "PUT", "/sim_cards/config/cfg_sim2")
    assert [call[2] for call in put] == [{"data": {"deny_roaming": "0"}}]


async def test_roaming_change_is_confirmed_by_reading_back(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    router_state: Any,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    writes = router_state(entry.runtime_data)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, "switch", "2-1.1_roaming_sim2")},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id(hass, "switch", "2-1.1_roaming_sim1")},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert writes == [("cfg_sim2", "0"), ("cfg_sim1", "1")]
    assert hass.states.get(entity_id(hass, "switch", "2-1.1_roaming_sim2")).state == (
        STATE_ON
    )
    assert hass.states.get(entity_id(hass, "switch", "2-1.1_roaming_sim1")).state == (
        STATE_OFF
    )


async def test_roaming_switches_need_the_page(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, sim_cards=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "switch", DOMAIN, f"{SERIAL}_2-1.1_roaming_sim1"
        )
        is None
    )
