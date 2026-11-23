"""Presence trackers: who is connected to the router's own Wi-Fi."""

from __future__ import annotations

import json
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teltonika_control.const import (
    CONF_PRESENCE_DELAY,
    CONF_PRESENCE_IDLE,
    CONF_SCAN_INTERVAL,
    CONF_TRACKED_DEVICES,
    DOMAIN,
)
from custom_components.teltonika_control.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.teltonika_control.models import (
    AssociatedDevice,
    ClientDevice,
    derive_associated,
    derive_clients,
    normalize_mac,
)

from .conftest import BASE, ENTRY_DATA, entity_id, mock_router
from .payloads import (
    DHCP_LEASES,
    SERIAL,
    WIRELESS_CONFIG,
    WIRELESS_DEVICES,
    WIRELESS_STATUS,
)
from .test_integration import setup_entry

# On the Wi-Fi in the sample answer, without a DHCP lease.
PHONE = "aa:bb:cc:dd:ee:01"
# Has a lease named "laptop" but is not on the Wi-Fi.
LAPTOP = "aa:bb:cc:00:00:01"
CLOCK = "custom_components.teltonika_control.coordinator._monotonic"


def tracking_entry(*macs: str, delay: int = 1, idle: int = 0) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id=SERIAL,
        title="Teltonika-RUTC50.com",
        options={
            CONF_TRACKED_DEVICES: list(macs),
            CONF_PRESENCE_DELAY: delay,
            CONF_PRESENCE_IDLE: idle,
        },
    )


def tracker(hass: HomeAssistant, mac: str) -> str:
    return entity_id(hass, "device_tracker", f"presence_{mac}")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("AA:BB:CC:DD:EE:01", "aa:bb:cc:dd:ee:01"),
        ("aa-bb-cc-dd-ee-01", "aa:bb:cc:dd:ee:01"),
        ("aabbccddee01", "aa:bb:cc:dd:ee:01"),
        ("aa:bb:cc", None),
        ("zz:bb:cc:dd:ee:01", None),
        ("aa:bb:cc:dd:ee:01:02", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_mac(value: Any, expected: str | None) -> None:
    assert normalize_mac(value) == expected


def test_associated_devices_come_from_the_access_points() -> None:
    found = derive_associated(WIRELESS_CONFIG, WIRELESS_STATUS, WIRELESS_DEVICES)

    assert found == {PHONE: AssociatedDevice(PHONE, "MyRouter", "2.4 GHz")}


def test_the_idle_time_of_a_device_is_read_in_seconds() -> None:
    status = [
        {
            "id": "default_radio0",
            "mode": "ap",
            "assoclist": {
                "AA:BB:CC:DD:EE:01": {"device": "radio0", "inactive": 470, "signal": -61},
                "AA:BB:CC:DD:EE:02": {"device": "radio0"},
            },
        }
    ]

    found = derive_associated(WIRELESS_CONFIG, status, WIRELESS_DEVICES)

    assert found[PHONE].inactive == 0.47
    assert found[PHONE].signal == -61
    assert found["aa:bb:cc:dd:ee:02"].inactive is None
    assert found["aa:bb:cc:dd:ee:02"].signal is None


def test_a_client_row_or_an_empty_access_point_adds_nothing() -> None:
    status = [
        {"id": "6", "mode": "sta", "assoclist": {"AA:BB:CC:DD:EE:09": {}}},
        {"id": "default_radio0", "mode": "ap", "assoclist": {}},
        {"id": "default_radio1", "mode": "ap"},
        {"id": "x", "mode": "ap", "assoclist": {"not a mac": {}}},
    ]

    assert derive_associated(WIRELESS_CONFIG, status, WIRELESS_DEVICES) == {}


def test_known_clients_join_leases_and_wifi_devices() -> None:
    associated = derive_associated(WIRELESS_CONFIG, WIRELESS_STATUS, WIRELESS_DEVICES)

    assert derive_clients(DHCP_LEASES, associated) == [
        ClientDevice(LAPTOP, "laptop", "192.168.1.10", False),
        ClientDevice("aa:bb:cc:00:00:02", None, "192.168.1.11", False),
        ClientDevice(PHONE, None, None, True),
    ]
    assert derive_clients(None, {}) == []


async def test_a_tracker_per_chosen_device_follows_the_wifi(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, tracking_entry(PHONE, LAPTOP))

    phone = hass.states.get(tracker(hass, PHONE))
    assert phone.state == "home"
    assert phone.attributes["source_type"] == "router"
    assert phone.attributes["mac"] == PHONE
    assert phone.attributes["wifi_network"] == "MyRouter"
    assert phone.attributes["wifi_band"] == "2.4 GHz"
    laptop = hass.states.get(tracker(hass, LAPTOP))
    assert laptop.state == "not_home"
    assert laptop.attributes["host_name"] == "laptop"
    assert laptop.attributes["ip"] == "192.168.1.10"
    assert "laptop" in laptop.name

    registry = er.async_get(hass)
    assert registry.async_get(tracker(hass, PHONE)).disabled_by is None


async def test_without_chosen_devices_there_are_no_trackers(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("device_tracker", DOMAIN, f"{SERIAL}_presence_{PHONE}")
        is None
    )


async def test_a_device_is_away_only_after_the_delay(
    hass: HomeAssistant,
    aioclient_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    monkeypatch.setattr(CLOCK, lambda: now[0])
    mock_router(aioclient_mock)
    entry = tracking_entry(PHONE)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    original = coordinator.client.async_wireless_status
    assert hass.states.get(tracker(hass, PHONE)).state == "home"

    async def nobody() -> list[dict[str, Any]]:
        return [{"id": "default_radio0", "mode": "ap", "assoclist": {}}]

    monkeypatch.setattr(coordinator.client, "async_wireless_status", nobody)
    for seconds, expected in ((30, "home"), (60, "home"), (61, "not_home")):
        now[0] = float(seconds)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(tracker(hass, PHONE)).state == expected, seconds

    monkeypatch.setattr(coordinator.client, "async_wireless_status", original)
    now[0] = 70.0
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(tracker(hass, PHONE)).state == "home"


async def test_a_silent_device_counts_as_gone_with_an_idle_limit(
    hass: HomeAssistant,
    aioclient_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The router keeps a phone that left without goodbye for minutes."""
    now = [0.0]
    monkeypatch.setattr(CLOCK, lambda: now[0])
    mock_router(aioclient_mock)
    entry = tracking_entry(PHONE, delay=1, idle=120)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    assert hass.states.get(tracker(hass, PHONE)).state == "home"

    def silent(seconds: float) -> Any:
        async def status() -> list[dict[str, Any]]:
            return [
                {
                    "id": "default_radio0",
                    "mode": "ap",
                    "assoclist": {
                        "AA:BB:CC:DD:EE:01": {
                            "device": "radio0",
                            "inactive": seconds * 1000,
                        }
                    },
                }
            ]

        return status

    caplog.set_level("DEBUG", logger="custom_components.teltonika_control.coordinator")
    # Quiet for 100 s: still within the limit, stays home.
    monkeypatch.setattr(coordinator.client, "async_wireless_status", silent(100))
    now[0] = 30.0
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(tracker(hass, PHONE)).state == "home"

    # Quiet for 200 s: no longer counted, away after the delay of one minute.
    monkeypatch.setattr(coordinator.client, "async_wireless_status", silent(200))
    for seconds, expected in ((60, "home"), (91, "not_home")):
        now[0] = float(seconds)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(tracker(hass, PHONE)).state == expected, seconds
    assert "idle_seconds=[200]" in caplog.text
    assert PHONE not in caplog.text.lower()

    # It talks again: home at once.
    monkeypatch.setattr(coordinator.client, "async_wireless_status", silent(2))
    now[0] = 95.0
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(tracker(hass, PHONE)).state == "home"


async def test_without_an_idle_limit_a_silent_device_stays_home(
    hass: HomeAssistant,
    aioclient_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    entry = tracking_entry(PHONE)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def status() -> list[dict[str, Any]]:
        return [
            {
                "id": "default_radio0",
                "mode": "ap",
                "assoclist": {"AA:BB:CC:DD:EE:01": {"device": "radio0", "inactive": 900000}},
            }
        ]

    monkeypatch.setattr(coordinator.client, "async_wireless_status", status)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(tracker(hass, PHONE)).state == "home"


async def test_the_tracker_shows_signal_and_silence_of_the_device(
    hass: HomeAssistant,
    aioclient_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_router(aioclient_mock)
    entry = tracking_entry(PHONE)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def status() -> list[dict[str, Any]]:
        return [
            {
                "id": "default_radio0",
                "mode": "ap",
                "assoclist": {
                    "AA:BB:CC:DD:EE:01": {
                        "device": "radio0",
                        "inactive": 12400,
                        "signal": -58,
                    }
                },
            }
        ]

    monkeypatch.setattr(coordinator.client, "async_wireless_status", status)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    attributes = hass.states.get(tracker(hass, PHONE)).attributes
    assert attributes["signal"] == -58
    assert attributes["inactive_seconds"] == 12


async def test_a_zero_delay_reports_away_at_once(
    hass: HomeAssistant,
    aioclient_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    monkeypatch.setattr(CLOCK, lambda: now[0])
    mock_router(aioclient_mock)
    entry = tracking_entry(PHONE, delay=0)
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data

    async def nobody() -> list[dict[str, Any]]:
        return [{"id": "default_radio0", "mode": "ap", "assoclist": {}}]

    monkeypatch.setattr(coordinator.client, "async_wireless_status", nobody)
    now[0] = 1.0
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(tracker(hass, PHONE)).state == "not_home"


async def test_presence_is_unknown_while_the_wifi_page_never_answered(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    aioclient_mock.get(f"{BASE}/wireless/interfaces/status", exc=TimeoutError())
    mock_router(aioclient_mock)
    await setup_entry(hass, tracking_entry(PHONE))

    assert hass.states.get(tracker(hass, PHONE)).state == "unavailable"


async def test_options_list_the_known_devices_and_save_the_choice(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    selector = next(
        value for key, value in result["data_schema"].schema.items()
        if key == CONF_TRACKED_DEVICES
    )
    options = selector.config["options"]
    assert [o["value"] for o in options] == [PHONE, LAPTOP, "aa:bb:cc:00:00:02"]
    assert options[0]["label"] == f"● ? ({PHONE})"
    assert options[1]["label"] == f"laptop ({LAPTOP})"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 30,
            CONF_TRACKED_DEVICES: [PHONE.upper(), PHONE, "AA-BB-CC-00-00-01"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_TRACKED_DEVICES] == [PHONE, LAPTOP]
    assert hass.states.get(tracker(hass, PHONE)).state == "home"
    assert hass.states.get(tracker(hass, LAPTOP)).state == "not_home"


async def test_options_reject_a_wrong_mac_address(
    hass: HomeAssistant, aioclient_mock: Any, entry: MockConfigEntry
) -> None:
    mock_router(aioclient_mock)
    await setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 30, CONF_TRACKED_DEVICES: ["not-a-mac"]},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TRACKED_DEVICES: "invalid_mac"}


async def test_a_device_taken_out_of_the_options_loses_its_tracker(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)
    entry = tracking_entry(PHONE, LAPTOP)
    await setup_entry(hass, entry)
    laptop = tracker(hass, LAPTOP)

    hass.config_entries.async_update_entry(
        entry, options={CONF_TRACKED_DEVICES: [PHONE], CONF_PRESENCE_DELAY: 1}
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert registry.async_get(laptop) is None
    assert hass.states.get(laptop) is None
    assert hass.states.get(tracker(hass, PHONE)).state == "home"


async def test_diagnostics_do_not_show_the_chosen_devices(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    mock_router(aioclient_mock)
    entry = tracking_entry(PHONE)
    await setup_entry(hass, entry)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["options"][CONF_TRACKED_DEVICES] == "**REDACTED**"
    assert PHONE not in json.dumps(result).lower()
