"""Downloading and installing router firmware."""

from __future__ import annotations

import time
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.api import (
    TeltonikaApiError,
    TeltonikaConnectionError,
)
from custom_components.teltonika_control.const import DOMAIN, FIRMWARE_INSTALL_GRACE
from custom_components.teltonika_control.models import derive_firmware_download

from .conftest import entity_id, find_device, mock_router
from .payloads import SERIAL
from .test_integration import requests, setup_entry


@pytest.mark.parametrize(
    ("raw", "process", "percent", "ready"),
    [
        ({"percents": "100", "process": "succeeded"}, "succeeded", 100, True),
        ({"percents": "40", "process": "downloading"}, "downloading", 40, False),
        ({"percents": "100", "process": "failed"}, "failed", 100, False),
        ({"percents": "100"}, None, 100, False),
    ],
)
def test_download_state_is_read(raw: dict[str, Any], process: Any, percent: int, ready: bool) -> None:
    download = derive_firmware_download(raw)
    assert download is not None
    assert (download.process, download.percent, download.ready) == (process, percent, ready)


@pytest.mark.parametrize("raw", [None, {}, [], "x"])
def test_no_download_state_without_data(raw: Any) -> None:
    assert derive_firmware_download(raw) is None


async def test_download_sensor_and_buttons(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    state = hass.states.get(entity_id(hass, "sensor", "firmware_state"))
    assert state.state == "ready"
    assert state.attributes["percent"] == 100
    assert state.attributes["installed_version"] == "RUTC_R_00.07.26.2"
    assert state.attributes["latest_version"] == "RUTC_R_00.07.27.1"
    assert hass.states.get(entity_id(hass, "button", "firmware_download")).state != "unavailable"


@pytest.mark.parametrize(
    ("progress", "firmware", "expected"),
    [
        ({"percents": "40", "process": "downloading"}, True, "downloading"),
        ({"percents": "0", "process": "idle"}, True, "update_available"),
        ({"percents": "100", "process": "failed"}, True, "failed"),
        ({"percents": "100", "process": "succeeded"}, {"device": {"stable_version": "RUTC_R_00.07.26.2"}}, "up_to_date"),
    ],
)
async def test_firmware_status_follows_the_download(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    progress: dict[str, Any],
    firmware: Any,
    expected: str,
) -> None:
    mock_router(aioclient_mock, firmware=firmware, firmware_progress=progress)
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "sensor", "firmware_state")).state == expected


async def test_installation_is_followed_until_the_router_runs_the_new_version(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    status = entity_id(hass, "sensor", "firmware_state")

    await coordinator.async_install_firmware()
    await hass.async_block_till_done()
    # The router still answers with the old version: the installation goes on.
    assert hass.states.get(status).state == "installing"
    assert hass.states.get(entity_id(hass, "button", "firmware_download")).state == "unavailable"

    coordinator._track_firmware("RUTC_R_00.07.27.1")
    assert coordinator.installing_since is None
    assert coordinator.router.firmware == "RUTC_R_00.07.27.1"
    device = find_device(hass, (DOMAIN, SERIAL))
    assert device.sw_version == "RUTC_R_00.07.27.1"


async def test_installation_that_never_restarts_is_reported_as_failed(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    await coordinator.async_install_firmware()
    coordinator.installing_since = time.monotonic() - FIRMWARE_INSTALL_GRACE - 1
    coordinator._track_firmware("RUTC_R_00.07.26.2")

    assert coordinator.firmware_state == "failed"
    # A new download clears the failure.
    coordinator.install_failed = False
    assert coordinator.firmware_state == "ready"


async def test_installation_that_cannot_be_started_does_not_stay_installing(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def refused(keep_settings: bool = True) -> None:
        raise TeltonikaApiError("Firmware file is invalid", status=400)

    monkeypatch.setattr(coordinator.client, "async_firmware_upgrade", refused)
    with pytest.raises(HomeAssistantError, match="invalid"):
        await coordinator.async_install_firmware()
    assert coordinator.installing_since is None


async def test_install_button_is_off_until_you_enable_it(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    install = registry.async_get(entity_id(hass, "button", "firmware_install"))
    assert install.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_download_button_asks_the_router_to_download(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "firmware_download")},
        blocking=True,
    )

    assert len(requests(aioclient_mock, "POST", "/firmware/actions/fota_download")) == 1
    assert not requests(aioclient_mock, "POST", "/firmware/actions/upgrade")


async def test_no_download_when_the_firmware_is_current(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(
        aioclient_mock,
        firmware={"device": {"stable_version": "RUTC_R_00.07.26.2"}},
    )
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "button", "firmware_download")).state == "unavailable"
    with pytest.raises(HomeAssistantError, match="no newer firmware"):
        await entry.runtime_data.async_download_firmware()
    with pytest.raises(HomeAssistantError, match="no newer firmware"):
        await entry.runtime_data.async_install_firmware()
    assert not requests(aioclient_mock, "POST", "/firmware/actions/fota_download")


async def test_install_keeps_the_settings(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    await entry.runtime_data.async_install_firmware()

    posts = requests(aioclient_mock, "POST", "/firmware/actions/upgrade")
    assert [call[2] for call in posts] == [{"data": {"keep_settings": "1"}}]


async def test_install_waits_for_a_complete_download(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, firmware_progress={"percents": "40", "process": "downloading"})
    await setup_entry(hass, entry)

    with pytest.raises(HomeAssistantError, match="Download the firmware first"):
        await entry.runtime_data.async_install_firmware()
    assert not requests(aioclient_mock, "POST", "/firmware/actions/upgrade")


async def test_lost_connection_while_the_router_restarts_is_not_an_error(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    async def restarting(keep_settings: bool = True) -> None:
        raise TeltonikaConnectionError("connection reset")

    monkeypatch.setattr(entry.runtime_data.client, "async_firmware_upgrade", restarting)
    await entry.runtime_data.async_install_firmware()


async def test_router_without_a_progress_page_has_no_firmware_actions(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock, firmware_progress=False)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    for platform, key in (
        ("button", "firmware_download"),
        ("button", "firmware_install"),
    ):
        assert registry.async_get_entity_id(platform, "teltonika_control", f"{SERIAL}_{key}") is None
