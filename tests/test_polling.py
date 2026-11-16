"""The router is polled gently: configuration pages are read rarely."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import CONF_CONFIG_INTERVAL, DOMAIN

from .conftest import ENTRY_DATA, mock_router
from .payloads import SERIAL
from .test_integration import requests, setup_entry

CONFIG_PAGES = (
    "/api/interfaces/config",
    "/wireless/interfaces/config",
    "/wireless/devices/status",
    "/api/wireguard/config",
)
STATUS_PAGES = (
    "/api/interfaces/status",
    "/wireless/interfaces/status",
    "/modems/status",
    "/system/device/usage/status",
    "/gps/position/status",
)


def counts(aioclient_mock: Any, pages: tuple[str, ...]) -> list[int]:
    return [len(requests(aioclient_mock, "GET", page)) for page in pages]


async def test_configuration_pages_are_not_read_on_every_poll(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    assert counts(aioclient_mock, CONFIG_PAGES) == [1, 1, 1, 1]
    assert counts(aioclient_mock, STATUS_PAGES) == [1, 1, 1, 1, 1]

    # A scheduled poll reads the status pages, not the configuration.
    await coordinator._async_update_data()
    assert counts(aioclient_mock, CONFIG_PAGES) == [1, 1, 1, 1]
    assert counts(aioclient_mock, STATUS_PAGES) == [2, 2, 2, 2, 2]


async def test_actions_read_the_configuration_again(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    await coordinator.async_refresh()

    assert counts(aioclient_mock, CONFIG_PAGES) == [2, 2, 2, 2]


async def test_configuration_interval_is_an_option(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id=SERIAL,
        options={CONF_CONFIG_INTERVAL: 30},
    )
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    assert coordinator._config_interval == 30

    # A short interval that has passed reads the configuration again.
    coordinator._fetched_at = {
        name: stamp - 60 for name, stamp in coordinator._fetched_at.items()
    }
    await coordinator._async_update_data()
    assert counts(aioclient_mock, CONFIG_PAGES) == [2, 2, 2, 2]
