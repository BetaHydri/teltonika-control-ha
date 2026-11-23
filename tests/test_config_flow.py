"""Tests for the config and options flows."""

from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import (
    CONF_CONFIG_INTERVAL,
    CONF_DATA_PLAN,
    CONF_PRESENCE_DELAY,
    CONF_PROBE_URL,
    CONF_SCAN_INTERVAL,
    CONF_TRACKED_DEVICES,
    CONF_VPN_HOST,
    CONF_VPN_PORT,
    DEFAULT_CONFIG_INTERVAL,
    DEFAULT_PRESENCE_DELAY,
    DEFAULT_VPN_PORT,
    DOMAIN,
)

from .conftest import ENTRY_DATA, mock_login_failure, mock_router, mock_unreachable
from .payloads import HOST, SERIAL


async def start_user_flow(hass: HomeAssistant) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)
    result = await start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Teltonika-RUTC50.com"
    assert result["result"].unique_id == SERIAL
    assert result["result"].state is ConfigEntryState.LOADED


async def test_user_flow_invalid_auth(hass: HomeAssistant, aioclient_mock: Any) -> None:
    mock_login_failure(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        (await start_user_flow(hass))["flow_id"], ENTRY_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect_then_recovers(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_unreachable(aioclient_mock)
    # The router is silent on plain HTTP as well, so there is nothing to fall back to.
    aioclient_mock.post(f"http://{HOST}/api/login", exc=aiohttp.ClientError("unreachable"))
    flow = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], ENTRY_DATA)
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    mock_router(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], ENTRY_DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_same_router_cannot_be_added_twice(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        (await start_user_flow(hass))["flow_id"], ENTRY_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_password(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-secret"


async def test_options_flow_disables_probe(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    # Emptying the URL field omits it from the submitted data.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_SCAN_INTERVAL: 60,
        CONF_CONFIG_INTERVAL: DEFAULT_CONFIG_INTERVAL,
        CONF_PROBE_URL: "",
        CONF_VPN_HOST: "",
        CONF_VPN_PORT: DEFAULT_VPN_PORT,
        CONF_DATA_PLAN: 0,
        CONF_TRACKED_DEVICES: [],
        CONF_PRESENCE_DELAY: DEFAULT_PRESENCE_DELAY,
    }
