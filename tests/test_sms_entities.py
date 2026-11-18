"""The SMS number and text fields, the send button and the result sensor."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.models import clean_phone_number

from .conftest import entity_id, mock_router
from .payloads import SERIAL
from .test_integration import requests, setup_entry


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("+49 170 1234567", "+491701234567"),
        ("0170-123 4567", "01701234567"),
        ("(0170) 123.4567", "01701234567"),
        ("hello", None),
        ("12", None),
        ("", None),
    ],
)
def test_phone_number_is_cleaned(text: str, expected: str | None) -> None:
    assert clean_phone_number(text) == expected


async def set_text(hass: HomeAssistant, key: str, value: str) -> None:
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": entity_id(hass, "text", key), "value": value},
        blocking=True,
    )


async def press_send(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "sms_send")},
        blocking=True,
    )


async def test_send_button_sends_the_typed_sms_and_clears_the_text(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    caplog.set_level(logging.DEBUG, logger="custom_components.teltonika_control")

    await set_text(hass, "sms_number", "+49 170 1234567")
    await set_text(hass, "sms_text", "Secret gate code 4711")
    await press_send(hass)

    assert requests(aioclient_mock, "POST", "/messages/actions/send")[0][2] == {
        "data": {
            "modem": "2-1.1",
            "number": "+491701234567",
            "message": "Secret gate code 4711",
        }
    }
    # The mock answers with two parts.
    assert hass.states.get(entity_id(hass, "sensor", "last_sms")).state == "Sent (2 parts)"
    assert hass.states.get(entity_id(hass, "text", "sms_text")).state == ""
    # The number stays for the next message.
    assert hass.states.get(entity_id(hass, "text", "sms_number")).state == "+49 170 1234567"
    assert "4711" not in caplog.text
    assert "1234567" not in caplog.text


async def test_send_button_refuses_an_empty_text_or_a_bad_number(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    last = entity_id(hass, "sensor", "last_sms")

    await set_text(hass, "sms_number", "hello")
    await set_text(hass, "sms_text", "x")
    with pytest.raises(HomeAssistantError, match="phone number"):
        await press_send(hass)
    assert hass.states.get(last).state == "Not sent: enter a phone number"

    await set_text(hass, "sms_number", "+491701234567")
    await set_text(hass, "sms_text", "   ")
    with pytest.raises(HomeAssistantError, match="text"):
        await press_send(hass)
    assert hass.states.get(last).state == "Not sent: enter a text"
    assert not requests(aioclient_mock, "POST", "/messages/actions/send")


async def test_failed_send_keeps_the_text_and_reports_the_reason(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    monkeypatch.setattr(entry.runtime_data, "modem_ids", lambda: ["a", "b"])

    await set_text(hass, "sms_number", "+491701234567")
    await set_text(hass, "sms_text", "hello")
    with pytest.raises(HomeAssistantError, match="Choose the modem"):
        await press_send(hass)

    assert hass.states.get(entity_id(hass, "text", "sms_text")).state == "hello"
    assert hass.states.get(entity_id(hass, "sensor", "last_sms")).state.startswith("Not sent:")


async def test_router_without_an_sms_page_has_no_sms_entities(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, sms=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    for platform, key in (
        ("text", "sms_number"),
        ("text", "sms_text"),
        ("button", "sms_send"),
        ("sensor", "last_sms"),
    ):
        assert registry.async_get_entity_id(platform, "teltonika_control", f"{SERIAL}_{key}") is None
