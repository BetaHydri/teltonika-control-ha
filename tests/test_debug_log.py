"""Debug logging: useful for support, and never with secrets."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.debug import describe_shape, shape_text
from custom_components.teltonika_control.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import entity_id, mock_router
from .test_integration import setup_entry

LOGGER = "custom_components.teltonika_control"
SECRETS = (
    "secret",  # router password
    "Bearer",
    "262010123456789",  # IMSI
    "864000000000001",  # IMEI
    "89490000000000000001",  # ICCID
    "MODEMSERIAL123",
    "CampWifi",  # SSID
    "10.1.2.3",  # uplink address
    "192.168.1.1",  # router address
)


def own_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == logging.DEBUG
    ]


def test_describe_shape_shows_structure_but_no_secrets() -> None:
    shape = describe_shape(
        {
            "imsi": "262010123456789",
            "pinleft": 3,
            "latitude": 48.43,
            "rxbytes": 1234,
            "operator_state": "Registered, home",
            "ssid": "CampWifi",
            "enabled": True,
            "ipaddrs": ["10.1.2.3/32"],
            "peers": [],
            "note": None,
        }
    )
    assert shape == {
        "enabled": True,
        "imsi": "str(15)",
        "ipaddrs": {"list": 1, "first": "str(11)"},
        "latitude": "<hidden>",
        "note": "null",
        "operator_state": "Registered, home",
        "peers": "[]",
        "pinleft": "<hidden>",
        "rxbytes": 1234,
        "ssid": "str(8)",
    }


def test_shape_text_is_cut() -> None:
    text = shape_text({f"key{i}": "x" for i in range(500)}, limit=100)
    assert text.endswith("...(cut)")
    assert len(text) < 120


async def test_debug_log_explains_the_router_and_hides_secrets(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    text = "\n".join(own_lines(caplog))
    assert "Logged in, the session token lasts" in text
    assert "GET /interfaces/status -> HTTP 200" in text
    assert "Answer structure of /modems/status:" in text
    assert "Router report: model=" in text
    assert "Pages: {" in text
    assert "Router report: modems=1" in text
    assert "Update: uplink=mobile" in text
    for secret in SECRETS:
        assert secret not in text, secret


async def test_the_answer_structure_is_logged_once_per_page(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    await entry.runtime_data.async_refresh()

    structure = [
        line for line in own_lines(caplog) if "Answer structure of /modems/status" in line
    ]
    requests_seen = [line for line in own_lines(caplog) if line.startswith("GET /modems/status ->")]
    assert len(structure) == 1
    assert len(requests_seen) >= 2


async def test_a_missing_page_is_explained(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    mock_router(aioclient_mock, gps=False)
    await setup_entry(hass, entry)

    text = "\n".join(own_lines(caplog))
    assert "Page gps is not available on this router (HTTP 404" in text
    assert "GET /gps/position/status -> HTTP 404" in text


async def test_an_action_is_logged_with_its_fields_only(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, "switch", "ap_default_radio1")},
        blocking=True,
    )

    text = "\n".join(own_lines(caplog))
    assert "Action: access point default_radio1 -> enabled=True" in text
    assert "PUT /wireless/interfaces/config/default_radio1 -> HTTP 200" in text
    assert "sending fields ['enabled']" in text


async def test_diagnostics_show_pages_and_structure_without_secrets(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
) -> None:
    mock_router(aioclient_mock, gps=False)
    await setup_entry(hass, entry)

    result = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(result)

    assert result["router_pages"]["modems"] == "ok"
    assert result["router_pages"]["gps"].startswith("missing (HTTP 404")
    assert "operator_state" in result["answer_structure"]["modems"]
    for secret in SECRETS[2:6]:
        assert secret not in text, secret
