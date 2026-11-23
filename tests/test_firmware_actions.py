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
from custom_components.teltonika_control.const import (
    DOMAIN,
    FIRMWARE_DOWNLOAD_SETTLE,
    FIRMWARE_INSTALL_GRACE,
)
from custom_components.teltonika_control.models import derive_firmware_download

from .conftest import BASE, entity_id, find_device, mock_router
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


async def test_status_keeps_going_when_the_update_page_fails_during_a_download(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock, firmware_progress={"percents": "0", "process": "idle"})
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    status = entity_id(hass, "sensor", "firmware_state")
    assert hass.states.get(status).state == "update_available"

    await coordinator.async_download_firmware()

    async def failing() -> dict[str, Any]:
        raise TeltonikaApiError("busy", status=500)

    async def running() -> dict[str, Any]:
        return {"percents": "35", "process": "downloading"}

    monkeypatch.setattr(coordinator.client, "async_firmware_updates", failing)
    monkeypatch.setattr(coordinator.client, "async_firmware_progress", running)
    coordinator._invalidate_config_pages()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(status)
    assert state.state == "downloading"
    assert state.attributes["percent"] == 35
    assert hass.states.get(entity_id(hass, "update", "firmware")).state != "unknown"


async def test_download_progress_alone_is_enough_for_the_status(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def failing() -> dict[str, Any]:
        raise TeltonikaApiError("busy", status=500)

    async def running() -> dict[str, Any]:
        return {"percents": "10", "process": "downloading"}

    monkeypatch.setattr(coordinator.client, "async_firmware_updates", failing)
    monkeypatch.setattr(coordinator.client, "async_firmware_progress", running)
    coordinator._invalidate_config_pages()
    await coordinator.async_refresh()

    assert coordinator.firmware_state == "downloading"


async def test_download_asks_for_the_release_the_server_actually_has(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    await entry.runtime_data.async_download_firmware()
    posts = requests(aioclient_mock, "POST", "/firmware/actions/fota_download")
    assert [call[2] for call in posts] == [{"data": {"type": "stable"}}]


async def test_download_asks_for_the_latest_when_there_is_no_stable_release(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    # The router's own default type is "stable", which would download nothing.
    mock_router(
        aioclient_mock,
        firmware={"device": {"version": "RUTC_R_00.07.28.1", "stable_version": "newest"}},
    )
    await setup_entry(hass, entry)
    await entry.runtime_data.async_download_firmware()
    posts = requests(aioclient_mock, "POST", "/firmware/actions/fota_download")
    assert [call[2] for call in posts] == [{"data": {"type": "latest"}}]


async def test_an_old_succeeded_does_not_count_until_the_progress_page_caught_up(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    assert coordinator.firmware_state == "ready"

    await coordinator.async_download_firmware()
    assert coordinator.firmware_state == "downloading"
    assert hass.states.get(entity_id(hass, "button", "firmware_install")) is None or (
        hass.states.get(entity_id(hass, "button", "firmware_install")).state == "unavailable"
    )

    coordinator.download_requested_at = time.monotonic() - FIRMWARE_DOWNLOAD_SETTLE - 1
    assert coordinator.firmware_state == "ready"


async def test_missing_firmware_file_makes_the_old_result_stale(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def refused(keep_settings: bool = True) -> None:
        raise TeltonikaApiError("Firmware file not found in the device.", status=400)

    monkeypatch.setattr(coordinator.client, "async_firmware_upgrade", refused)
    with pytest.raises(HomeAssistantError, match="not found"):
        await coordinator.async_install_firmware()

    assert coordinator.firmware_state == "update_available"
    with pytest.raises(HomeAssistantError, match="Download the firmware first"):
        await coordinator.async_install_firmware()


NOT_FOUND = {
    "success": False,
    "errors": [{"code": 1, "error": "Firmware file not found in the device."}],
}


async def test_the_downloaded_file_is_checked_once_and_the_status_stays_ready(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    for _ in range(3):
        await coordinator.async_refresh()

    assert hass.states.get(entity_id(hass, "sensor", "firmware_state")).state == "ready"
    assert len(requests(aioclient_mock, "POST", "/firmware/actions/verify")) == 1
    assert not requests(aioclient_mock, "POST", "/firmware/actions/upgrade")


async def test_a_file_that_is_gone_is_not_called_ready(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    """The router's progress page says succeeded for a file it no longer has."""
    aioclient_mock.post(f"{BASE}/firmware/actions/verify", status=400, json=NOT_FOUND)
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    assert hass.states.get(entity_id(hass, "sensor", "firmware_state")).state == (
        "update_available"
    )
    with pytest.raises(HomeAssistantError, match="Download the firmware first"):
        await coordinator.async_install_firmware()
    assert not requests(aioclient_mock, "POST", "/firmware/actions/upgrade")

    # A new download starts over and is checked again once it is complete.
    await coordinator.async_download_firmware()
    coordinator.download_requested_at = time.monotonic() - FIRMWARE_DOWNLOAD_SETTLE - 1
    assert coordinator.firmware_state == "ready"


async def test_an_unclear_answer_keeps_the_status_and_is_asked_again_later(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    aioclient_mock.post(
        f"{BASE}/firmware/actions/verify",
        status=500,
        json={"success": False, "errors": [{"code": 5, "error": "busy"}]},
    )
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    assert hass.states.get(entity_id(hass, "sensor", "firmware_state")).state == "ready"
    assert len(requests(aioclient_mock, "POST", "/firmware/actions/verify")) == 1

    await coordinator.async_refresh()
    assert len(requests(aioclient_mock, "POST", "/firmware/actions/verify")) == 1

    coordinator._file_check_retry_at = 0.0
    await coordinator.async_refresh()
    assert len(requests(aioclient_mock, "POST", "/firmware/actions/verify")) == 2
    assert coordinator.firmware_state == "ready"


async def test_no_check_while_the_firmware_is_up_to_date(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(
        aioclient_mock,
        firmware={"device": {"stable_version": "RUTC_R_00.07.26.2"}},
        firmware_progress={"percents": "100", "process": "succeeded"},
    )
    await setup_entry(hass, entry)

    assert not requests(aioclient_mock, "POST", "/firmware/actions/verify")


async def test_install_with_a_gone_file_explains_what_to_do(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def refused(keep_settings: bool = True) -> None:
        raise TeltonikaApiError("Firmware file not found in the device.", status=400)

    monkeypatch.setattr(coordinator.client, "async_firmware_upgrade", refused)
    with pytest.raises(HomeAssistantError, match="Download firmware again"):
        await coordinator.async_install_firmware()


async def test_status_is_up_to_date_when_the_versions_cannot_be_compared(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    # After an update the router lists no newer release; its old "succeeded"
    # must not make the status say "ready".
    mock_router(aioclient_mock, firmware={"device": {"stable_version": "newest"}})
    await setup_entry(hass, entry)

    assert hass.states.get(entity_id(hass, "sensor", "firmware_state")).state == "up_to_date"


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
