"""Tests for the VPN reachability check."""

from __future__ import annotations

import json
from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.config_flow import parse_vpn_target
from custom_components.teltonika_control.const import (
    CONF_PROBE_URL,
    CONF_SCAN_INTERVAL,
    CONF_VPN_HOST,
    CONF_VPN_PORT,
    DOMAIN,
)
from custom_components.teltonika_control.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import ENTRY_DATA, entity_id, mock_router
from .payloads import SERIAL


class FakeWriter:
    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


def patch_connection(
    monkeypatch: pytest.MonkeyPatch, outcome: BaseException | None
) -> list[tuple[str, int]]:
    """Replace the TCP connect; raise ``outcome`` or succeed."""
    calls: list[tuple[str, int]] = []

    async def fake_open_connection(host: str, port: int) -> tuple[None, FakeWriter]:
        calls.append((host, port))
        if outcome is not None:
            raise outcome
        return None, FakeWriter()

    monkeypatch.setattr("asyncio.open_connection", fake_open_connection)
    return calls


def vpn_entry(**options: Any) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id=SERIAL,
        title="Teltonika-RUTC50.com",
        options=options,
    )


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_reachable_tunnel(
    hass: HomeAssistant, aioclient_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_router(aioclient_mock)
    calls = patch_connection(monkeypatch, None)
    await setup(hass, vpn_entry(**{CONF_VPN_HOST: "homebase.example.net", CONF_VPN_PORT: 8443}))

    assert calls == [("homebase.example.net", 8443)]
    assert hass.states.get(entity_id(hass, "binary_sensor", "vpn_reachable")).state == (
        STATE_ON
    )
    assert float(hass.states.get(entity_id(hass, "sensor", "vpn_latency")).state) >= 0


async def test_refused_connection_still_counts_as_reachable(
    hass: HomeAssistant, aioclient_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_router(aioclient_mock)
    patch_connection(monkeypatch, ConnectionRefusedError())
    await setup(hass, vpn_entry(**{CONF_VPN_HOST: "192.168.178.1"}))

    assert hass.states.get(entity_id(hass, "binary_sensor", "vpn_reachable")).state == (
        STATE_ON
    )
    assert hass.states.get(entity_id(hass, "sensor", "vpn_latency")).state != (
        STATE_UNKNOWN
    )


@pytest.mark.parametrize("failure", [TimeoutError(), OSError("no route to host")])
async def test_unreachable_tunnel(
    hass: HomeAssistant,
    aioclient_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    mock_router(aioclient_mock)
    patch_connection(monkeypatch, failure)
    await setup(hass, vpn_entry(**{CONF_VPN_HOST: "fd00::1"}))

    assert hass.states.get(entity_id(hass, "binary_sensor", "vpn_reachable")).state == (
        STATE_OFF
    )
    assert hass.states.get(entity_id(hass, "sensor", "vpn_latency")).state == (
        STATE_UNKNOWN
    )


async def test_no_vpn_entities_without_a_host(
    hass: HomeAssistant, aioclient_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_router(aioclient_mock)
    calls = patch_connection(monkeypatch, None)
    await setup(hass, vpn_entry())

    assert not calls
    registry = hass.data["entity_registry"]
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, f"{SERIAL}_vpn_reachable") is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{SERIAL}_vpn_latency") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("homebase.example.net", ("homebase.example.net", None)),
        ("homebase.example.net:8443", ("homebase.example.net", 8443)),
        ("192.168.178.1", ("192.168.178.1", None)),
        ("192.168.178.1:80", ("192.168.178.1", 80)),
        ("fd00::1", ("fd00::1", None)),
        ("[fd00::1]", ("fd00::1", None)),
        ("[fd00::1]:443", ("fd00::1", 443)),
        ("  fritz.box  ", ("fritz.box", None)),
        ("", None),
        ("https://fritz.box", None),
        ("fritz.box/admin", None),
        ("fritz box", None),
        ("fritz.box:abc", None),
        ("fritz.box:70000", None),
    ],
)
def test_parse_vpn_target(text: str, expected: tuple[str, int | None] | None) -> None:
    assert parse_vpn_target(text) == expected


async def test_diagnostics_hide_the_vpn_host(
    hass: HomeAssistant, aioclient_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_router(aioclient_mock)
    patch_connection(monkeypatch, None)
    entry = vpn_entry(**{CONF_VPN_HOST: "w52.example.net", CONF_VPN_PORT: 80})
    await setup(hass, entry)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["options"][CONF_VPN_HOST] == "**REDACTED**"
    assert result["vpn_reachable"] is True
    assert "w52.example.net" not in json.dumps(result)
    assert "secret" not in json.dumps(result)


async def test_options_flow_stores_the_vpn_target(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    patch_connection(monkeypatch, None)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 30,
            CONF_PROBE_URL: "",
            CONF_VPN_HOST: "[fd00::1]:8443",
            CONF_VPN_PORT: 443,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_VPN_HOST] == "fd00::1"
    assert entry.options[CONF_VPN_PORT] == 8443


async def test_options_flow_rejects_an_invalid_vpn_host(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 30, CONF_VPN_HOST: "https://fritz.box"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_VPN_HOST: "invalid_vpn_host"}
