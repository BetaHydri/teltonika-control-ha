"""Network registration and roaming state of the modem."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.models import (
    modem_is_roaming,
    modem_registration,
)

from .conftest import entity_id, mock_router
from .test_integration import setup_entry


@pytest.mark.parametrize(
    ("modem", "text", "roaming"),
    [
        ({"operator_state": "Registered, home"}, "Registered, home", False),
        ({"operator_state": "Registered, roaming"}, "Registered, roaming", True),
        ({"netstate": "Registered, Roaming"}, "Registered, Roaming", True),
        ({"operator_state": "Not registered"}, "Not registered", False),
        ({"operator_state": ""}, None, None),
        ({}, None, None),
    ],
)
def test_registration_and_roaming(
    modem: dict[str, Any], text: str | None, roaming: bool | None
) -> None:
    assert modem_registration(modem) == text
    assert modem_is_roaming(modem) is roaming


async def test_registration_and_roaming_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    registration = entity_id(hass, "sensor", "2-1.1_registration")
    roaming = entity_id(hass, "binary_sensor", "2-1.1_roaming")
    assert hass.states.get(registration).state == "Registered, home"
    assert hass.states.get(roaming).state == STATE_OFF

    coordinator.data.modems[0]["operator_state"] = "Registered, roaming"
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    assert hass.states.get(registration).state == "Registered, roaming"
    assert hass.states.get(roaming).state == STATE_ON
