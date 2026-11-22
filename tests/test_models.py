"""Tests for the state derivation logic."""

from __future__ import annotations

import pytest

from custom_components.teltonika_control.models import (
    AccessPoint,
    GpsPosition,
    RouterInfo,
    SavedNetwork,
    TeltonikaData,
    build_scan_networks,
    derive_gps,
    derive_portal_state,
    derive_saved_networks,
    derive_uplink,
    derive_wifi_client,
    derive_wifi_first,
    is_protected_interface,
    modem_temperature,
    multi_ap_priorities_first,
    next_multi_ap_priority,
    normalize_band,
    radio_occupant,
    wifi_network_names,
)

from .payloads import (
    DEVICE_STATUS,
    GPS_STATUS,
    INTERFACES_CONFIG,
    INTERFACES_STATUS,
    WIRELESS_CONFIG,
    WIRELESS_DEVICES,
    payloads,
)


def build(**kwargs) -> TeltonikaData:
    data = payloads(**kwargs)
    return TeltonikaData.build(
        interfaces=data["interfaces"],
        interface_config=data["config"],
        wireless_config=data["wireless_config"],
        wireless_status=data["wireless_status"],
        wireless_devices=data["wireless_devices"],
        modems=data["modems"],
        gps=data["gps"],
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"frequency": 2437}, "2.4 GHz"),
        ({"frequency": 5180}, "5 GHz"),
        ({"frequency": 5955}, "6 GHz"),
        ({"frequency": "5.18"}, "5 GHz"),
        ({"band": "2g"}, "2.4 GHz"),
        ({"band": "5g"}, "5 GHz"),
        ({"band": "11a"}, "5 GHz"),
        ({"channel": 6}, "2.4 GHz"),
        ({"channel": 36}, "5 GHz"),
        ({}, None),
    ],
)
def test_normalize_band(kwargs, expected) -> None:
    assert normalize_band(**kwargs) == expected


def test_router_info_from_device_status() -> None:
    info = RouterInfo.from_device_status("192.168.1.1", DEVICE_STATUS)
    assert info.unique_id == "1234567890"
    assert info.model == "RUTC50"
    assert info.firmware == "RUTC_R_00.07.26.2"
    assert info.name == "Teltonika-RUTC50.com"


def test_router_info_falls_back_to_host() -> None:
    info = RouterInfo.from_device_status("10.0.0.1", {})
    assert info.unique_id == "10.0.0.1"
    assert info.name == "10.0.0.1"


def test_uplink_is_mobile_when_wifi_has_worse_metric() -> None:
    networks = wifi_network_names(WIRELESS_CONFIG)
    uplink = derive_uplink(INTERFACES_STATUS, networks)
    assert uplink is not None
    assert (uplink.kind, uplink.ip, uplink.metric) == ("mobile", "10.1.2.3", 4)


def test_uplink_is_wifi_with_best_metric() -> None:
    data = build(wifi_metric=0)
    assert data.uplink is not None
    assert (data.uplink.kind, data.uplink.name) == ("wifi", "wifi4")
    assert data.uplink.ip == "192.168.50.20"


def test_no_default_route_means_no_uplink() -> None:
    assert derive_uplink([{"id": "lan", "name": "lan"}], set()) is None


@pytest.mark.parametrize(("wifi_metric", "expected"), [(10, False), (0, True)])
def test_wifi_first(wifi_metric, expected) -> None:
    assert build(wifi_metric=wifi_metric).wifi_first is expected


def test_wifi_first_unknown_without_saved_wifi() -> None:
    assert derive_wifi_first(INTERFACES_STATUS, INTERFACES_CONFIG, set()) is None


def test_wifi_client() -> None:
    client = build().wifi_client
    assert client is not None
    assert client.ssid == "CampWifi"
    assert client.signal == -61
    assert client.bitrate == 78
    assert client.band == "2.4 GHz"


def test_wifi_client_falls_back_to_the_configuration_when_status_is_missing() -> None:
    data = payloads(wifi_metric=0)
    built = TeltonikaData.build(
        interfaces=data["interfaces"],
        interface_config=data["config"],
        wireless_config=data["wireless_config"],
        wireless_status=[],
        wireless_devices=data["wireless_devices"],
        modems=data["modems"],
    )
    client = built.wifi_client
    assert client is not None
    assert client.ssid == "CampWifi"
    assert client.band == "2.4 GHz"
    assert client.signal is None
    assert client.bitrate is None


def test_no_wifi_client_when_not_associated() -> None:
    data = payloads()
    data["wireless_status"][0]["wpa_state"] = "SCANNING"
    built = TeltonikaData.build(
        interfaces=data["interfaces"],
        interface_config=data["config"],
        wireless_config=data["wireless_config"],
        wireless_status=data["wireless_status"],
        wireless_devices=data["wireless_devices"],
        modems=data["modems"],
    )
    assert built.wifi_client is None


def test_access_points_report_real_state_and_band() -> None:
    points = {p.config_id: p for p in build().access_points}
    assert points["default_radio0"].enabled is True
    assert points["default_radio0"].band == "2.4 GHz"
    # The 5 GHz access point is off, so its band comes from the radio.
    assert points["default_radio1"].enabled is False
    assert points["default_radio1"].band == "5 GHz"
    assert points["default_radio1"].label == "MyRouter 5 GHz"


def test_access_point_label_without_band() -> None:
    point = AccessPoint("x", None, True, "radio3", None)
    assert point.label == "x radio3"


@pytest.mark.parametrize(
    ("raw", "celsius"), [(450, 45.0), (45, 45.0), (-5, -5.0), (None, None)]
)
def test_modem_temperature(raw, celsius) -> None:
    assert modem_temperature({"temperature": raw}) == celsius


def test_stations_map_network_to_interface() -> None:
    stations = build().stations
    assert [(s.config_id, s.interface_id) for s in stations] == [("6", "wan2")]


@pytest.mark.parametrize(
    ("waiting", "wifi", "uplink_kind", "internet", "expected"),
    [
        (True, False, None, None, "waiting"),
        (False, False, None, None, "no_wifi"),
        (False, False, "wifi", True, "online"),
        (False, False, "wifi", False, "login_required"),
        (False, True, "wifi", False, "login_required"),
        (False, True, "wifi", True, "online"),
        (False, True, "mobile", True, "idle"),
    ],
)
def test_portal_state(waiting, wifi, uplink_kind, internet, expected) -> None:
    data = build(wifi_metric=0 if uplink_kind == "wifi" else None)
    if not wifi:
        data.wifi_client = None
    if uplink_kind is None:
        data.uplink = None
    data.portal_waiting = waiting
    data.internet = internet
    assert data.portal_state == expected
    assert (
        derive_portal_state(
            waiting=waiting,
            wifi_client=data.wifi_client,
            uplink=data.uplink,
            internet=internet,
        )
        == expected
    )


def test_radio_occupant_finds_client_and_multi_ap_but_not_access_points() -> None:
    config = [
        *WIRELESS_CONFIG,
        {"id": "m1", "mode": "multi_ap", "device": "radio1", "network": "wifi5"},
    ]

    assert radio_occupant(config, "radio0")["id"] == "6"
    assert radio_occupant(config, "radio1")["id"] == "m1"
    assert radio_occupant(WIRELESS_CONFIG, "radio1") is None
    assert radio_occupant([], "radio0") is None


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        ([], 1),
        ([{"priority": "3"}, {"priority": 7}, {"priority": "x"}, {}], 8),
    ],
)
def test_next_multi_ap_priority(entries, expected) -> None:
    assert next_multi_ap_priority(entries) == expected


@pytest.mark.parametrize(
    ("entries", "ssid", "expected"),
    [
        ([], "Camp", {}),
        ([{"id": "a", "ssid": "Camp", "priority": "1"}], "Camp", {}),
        (
            [
                {"id": "a", "ssid": "Home", "priority": "1"},
                {"id": "b", "ssid": "Camp", "priority": "2"},
            ],
            "Camp",
            {"b": 1, "a": 2},
        ),
        (
            [
                {"id": "a", "ssid": "Home", "priority": "5"},
                {"id": "b", "ssid": "Camp", "priority": "9"},
                {"id": "c", "ssid": "Other", "priority": "7"},
            ],
            "Camp",
            {"b": 1, "a": 2, "c": 3},
        ),
        (
            [
                {"id": "a", "ssid": "Home", "priority": "1"},
                {"id": "b", "ssid": "Camp", "priority": "2"},
            ],
            "Home",
            {},
        ),
        ([{"id": "a", "ssid": "Home"}, {"id": "b", "ssid": "Camp"}], "Camp", {"b": 1, "a": 2}),
    ],
)
def test_multi_ap_priorities_first(entries, ssid, expected) -> None:
    assert multi_ap_priorities_first(entries, ssid) == expected


@pytest.mark.parametrize(
    ("interface_id", "protected"),
    [
        ("wan1", True),
        ("LAN", True),
        ("mob1s1a1", True),
        ("VPN_1", True),
        ("wifi4", False),
        ("wifi_camp", False),
    ],
)
def test_is_protected_interface(interface_id, protected) -> None:
    assert is_protected_interface(interface_id) is protected


def test_derive_gps_converts_the_string_values_of_the_router() -> None:
    position = derive_gps(GPS_STATUS)

    assert position == GpsPosition(
        latitude=48.436849,
        longitude=13.110672,
        altitude=350.4,
        speed=3.6,
        accuracy=0.6,
        satellites=7,
        heading=92.0,
        fix_status="3",
    )


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {},
        {"latitude": "0", "longitude": "0", "satellites": "0"},
        {"latitude": "", "longitude": "13.1"},
        {"latitude": "91.0", "longitude": "13.1"},
        {"latitude": "48.4", "longitude": "181"},
        {"latitude": "north", "longitude": "east"},
    ],
)
def test_derive_gps_without_a_usable_fix(raw) -> None:
    assert derive_gps(raw) is None


def test_derive_gps_accepts_other_heading_names_and_missing_values() -> None:
    position = derive_gps({"latitude": 48.4, "longitude": 13.1, "course": "10"})

    assert position is not None
    assert position.heading == 10.0
    assert position.speed is None
    assert position.satellites is None


def test_gps_available_even_without_a_fix() -> None:
    data = build()
    assert data.gps is not None and data.gps_available

    no_fix = TeltonikaData.build(
        interfaces=[],
        interface_config=[],
        wireless_config=[],
        wireless_status=[],
        wireless_devices=[],
        modems=[],
        gps={"latitude": "0", "longitude": "0"},
    )
    assert no_fix.gps is None
    assert no_fix.gps_available

    assert not TeltonikaData.build(
        interfaces=[],
        interface_config=[],
        wireless_config=[],
        wireless_status=[],
        wireless_devices=[],
        modems=[],
    ).gps_available


MIXED_CONFIG = [
    {
        "id": "6",
        "mode": "sta",
        "ssid": "ArtSpot",
        "network": "wifi4",
        "device": ["radio0"],
    },
    {"id": "m1", "mode": "multi_ap", "ssid": "", "network": "wifi5", "device": ["radio1"]},
]
MIXED_STATUS = [
    {
        "id": "6",
        "mode": "sta",
        "ssid": "ArtSpot",
        "wpa_state": "COMPLETED",
        "signal": -66,
        "bitrate": 117000000,
        "freq": 2437,
    },
    {
        "id": "m1",
        "mode": "multi_ap",
        "ssid": "ArtSpot",
        "wpa_state": "COMPLETED",
        "signal": -78,
        "bitrate": 6000000,
        "freq": 5180,
    },
]


@pytest.mark.parametrize(
    ("uplink", "band", "signal"),
    [
        ("wifi4", "2.4 GHz", -66),
        ("wifi5", "5 GHz", -78),
        (None, "2.4 GHz", -66),
        ("unrelated", "2.4 GHz", -66),
    ],
)
def test_wifi_client_is_the_connection_that_carries_the_uplink(
    uplink, band, signal
) -> None:
    client = derive_wifi_client(MIXED_STATUS, MIXED_CONFIG, WIRELESS_DEVICES, uplink)

    assert client is not None
    assert (client.band, client.signal) == (band, signal)
    assert client.ssid == "ArtSpot"


def test_saved_networks_list_clients_and_multi_ap_entries() -> None:
    saved = derive_saved_networks(
        [*WIRELESS_CONFIG, MIXED_CONFIG[1]],
        [{"id": "cfg1", "ssid": "Home"}, {"id": "cfg2", "ssid": ""}],
        WIRELESS_DEVICES,
    )

    assert [(s.label, s.kind, s.config_id, s.band) for s in saved] == [
        ("CampWifi (2.4 GHz)", "client", "6", "2.4 GHz"),
        ("Home (5 GHz, Multi AP)", "multi_ap", None, "5 GHz"),
    ]


def test_scan_networks_are_unique_per_band_sorted_and_hide_saved_ones() -> None:
    results = [
        {"ssid": "Camp", "bssid": "a", "signal": -70, "band": "5 GHz", "encrypted": True, "radio": "radio1"},
        {"ssid": "Camp", "bssid": "b", "signal": -55, "band": "5 GHz", "encrypted": True, "radio": "radio1"},
        {"ssid": "Camp", "bssid": "c", "signal": -60, "band": "2.4 GHz", "encrypted": True, "radio": "radio0"},
        {"ssid": "Free", "bssid": "d", "signal": -80, "band": "2.4 GHz", "encrypted": False, "radio": "radio0"},
        {"ssid": "", "bssid": "e", "signal": -40, "band": "2.4 GHz", "encrypted": False, "radio": "radio0"},
        {"ssid": "Known", "bssid": "f", "signal": -30, "band": "2.4 GHz", "encrypted": True, "radio": "radio0"},
    ]
    saved = [SavedNetwork("Known (2.4 GHz)", "Known", "client", "6", "2.4 GHz")]

    networks, seen, hidden = build_scan_networks(results, saved)

    assert [n.label for n in networks] == [
        "Camp [5 GHz · secured · -55 dBm]",
        "Camp [2.4 GHz · secured · -60 dBm]",
        "Free [2.4 GHz · open · -80 dBm]",
    ]
    assert (seen, hidden) == (4, 1)
    assert networks[0].bssid == "b"
    assert networks[2].encrypted is False
