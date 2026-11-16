"""Sample RutOS payloads shaped like the real API answers (anonymised)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

HOST = "192.168.1.1"
BASE = f"https://{HOST}/api"
PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
SERIAL = "1234567890"

DEVICE_STATUS = {
    "mnfinfo": {"serial": SERIAL, "mac": "001E42000001", "name": "RUTC5000XXXX"},
    "static": {
        "fw_version": "RUTC_R_00.07.26.2",
        "device_name": "RUTC50",
        "hostname": "Teltonika-RUTC50.com",
    },
}

INTERFACES_STATUS = [
    {
        "id": "mob1s1a1",
        "name": "mob1s1a1",
        "up": True,
        "metric": 4,
        "route": [{"target": "0.0.0.0", "mask": 0}],
        "ipaddrs": ["10.1.2.3/32"],
    },
    {"id": "lan", "name": "lan", "up": True, "ipaddrs": ["192.168.1.1/24"]},
    {
        "id": "wan2",
        "name": "wifi4",
        "up": True,
        "metric": 10,
        "route": [{"target": "0.0.0.0", "mask": 0}],
        "ipaddrs": ["192.168.50.20/24"],
    },
]

INTERFACES_CONFIG = [
    {"id": "mob1s1a1", "metric": "4"},
    {"id": "wan2", "metric": "10"},
]

WIRELESS_CONFIG = [
    {
        "id": "default_radio0",
        "mode": "ap",
        "ssid": "MyRouter",
        "network": "lan",
        "device": ["radio0"],
        "enabled": "1",
    },
    {
        "id": "default_radio1",
        "mode": "ap",
        "ssid": "MyRouter",
        "network": "lan",
        "device": ["radio1"],
        "enabled": "0",
    },
    {
        "id": "6",
        "mode": "sta",
        "ssid": "CampWifi",
        "network": "wifi4",
        "device": ["radio0"],
    },
]

WIRELESS_STATUS = [
    {
        "id": "6",
        "mode": "sta",
        "wpa_state": "COMPLETED",
        "ssid": "CampWifi",
        "signal": -61,
        "bitrate": 78000000,
        "freq": 2437,
        "channel": 6,
    },
    {"id": "default_radio0", "mode": "ap", "freq": 2437, "channel": 6},
]

WIRELESS_DEVICES = [
    {"id": "radio0", "band": "2g", "frequency": 2437},
    {"id": "radio1", "band": "5g", "frequency": 5180},
]

MODEMS = [
    {
        "id": "2-1.1",
        "name": "Quectel RG500Q",
        "model": "RG500Q",
        "manufacturer": "Quectel",
        "sim_count": 2,
        "active_sim": 1,
        "simstate": "Inserted",
        "data_conn_state": "Connected",
        "conntype": "5G (NSA)",
        "operator": "Testnet",
        "operator_state": "Registered, home",
        "band": "LTE B3",
        "rssi": -67,
        "rsrp": -104,
        "rsrq": -10,
        "sinr": 2,
        "temperature": 450,
        "rxbytes": 1048576,
        "txbytes": 524288,
    }
]

GPS_STATUS = {
    "latitude": "48.436849",
    "longitude": "13.110672",
    "altitude": "350.4",
    "speed": "3.6",
    "accuracy": "0.6",
    "satellites": "7",
    "angle": "92",
    "fix_status": "3",
}

SCAN_RESULT = [
    {
        "ssid": "CafeFreeWifi",
        "bssid": "00:11:22:33:44:55",
        "signal": -55,
        "channel": 11,
        "quality": 50,
        "encryption": {"enabled": False},
        "encryption_description": "None",
    }
]


USAGE_STATUS = {
    "load": {"min1": 0.33, "min5": 0.42, "min15": 0.44},
    "loadavg": 0.0864,
    "localtime": 1794839356,
    "memory": {"ram_percentage": 39.17, "flash_percentage": 1.64},
    "uptime": "5h 35m",
    "uptime_seconds": 20117,
}

DHCP_LEASES = [
    {
        "expires": 2070,
        "hostname": "laptop",
        "interface": "lan",
        "ipaddr": "192.168.1.10",
        "macaddr": "AA:BB:CC:00:00:01",
    },
    {
        "expires": 900,
        "hostname": "",
        "interface": "lan",
        "ipaddr": "192.168.1.11",
        "macaddr": "AA:BB:CC:00:00:02",
    },
]

WIREGUARD_CONFIG = [
    {"id": "HOMEBASE", "enabled": "1", "listen_port": "51820"},
    {"id": "SPARE", "enabled": "0", "listen_port": "51821"},
]

WIREGUARD_INTERFACE = {
    "id": "HOMEBASE",
    "name": "HOMEBASE",
    "proto": "wireguard",
    "up": True,
    "is_up": True,
    "rx_bytes": 4088912,
    "tx_bytes": 10434104,
    "uptime": 19695,
    "ipaddrs": ["10.0.0.2/24"],
}


def payloads(*, wifi_metric: int | None = None, wireguard: bool = True) -> dict[str, Any]:
    """Return fresh copies; optionally give Wi-Fi a better metric than mobile."""
    data = {
        "interfaces": deepcopy(INTERFACES_STATUS),
        "config": deepcopy(INTERFACES_CONFIG),
        "wireless_config": deepcopy(WIRELESS_CONFIG),
        "wireless_status": deepcopy(WIRELESS_STATUS),
        "wireless_devices": deepcopy(WIRELESS_DEVICES),
        "modems": deepcopy(MODEMS),
        "gps": deepcopy(GPS_STATUS),
        "usage": deepcopy(USAGE_STATUS),
        "dhcp": deepcopy(DHCP_LEASES),
        "wireguard": deepcopy(WIREGUARD_CONFIG),
    }
    if wireguard:
        data["interfaces"].append(deepcopy(WIREGUARD_INTERFACE))
    if wifi_metric is not None:
        data["interfaces"][2]["metric"] = wifi_metric
        data["config"][1]["metric"] = str(wifi_metric)
    return data
