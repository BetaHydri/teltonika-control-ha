"""Sample RutOS payloads shaped like the real API answers (anonymised)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

HOST = "192.168.1.1"
BASE = f"https://{HOST}/api"
PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
SERIAL = "1234567890"

DEVICE_STATUS = {
    "mnfinfo": {
        "serial": SERIAL,
        "mac": "001E42000001",
        "macEth": "001E42000002",
        "name": "RUTC5000XXXX",
    },
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
    {"id": "mob1s1a1", "metric": "4", "modem": "2-1.1", "sim": "1"},
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
    {
        "id": "default_radio0",
        "mode": "ap",
        "freq": 2437,
        "channel": 6,
        "assoclist": {"AA:BB:CC:DD:EE:01": {"device": "radio0", "tx_rate": 54000000}},
    },
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
        "imsi": "262010123456789",
        "imei": "864000000000001",
        "iccid": "89490000000000000001",
        "serial": "MODEMSERIAL123",
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


SIM_CARDS = [
    {
        ".type": "sim",
        "id": "cfg_sim1",
        "modem": "2-1.1",
        "position": "1",
        "primary": "1",
        "deny_roaming": "0",
    },
    {
        ".type": "sim",
        "id": "cfg_sim2",
        "modem": "2-1.1",
        "position": "2",
        "primary": "0",
        "deny_roaming": "1",
    },
]


PORT_FORWARDS = [
    {
        ".type": "redirect",
        "id": "cfg_ssh",
        "name": "SSH to the NAS",
        "enabled": "1",
        "proto": ["tcp"],
        "src_dport": "2222",
        "dest_ip": "192.168.1.20",
        "dest_port": "22",
    },
    {
        ".type": "redirect",
        "id": "cfg_web",
        "name": "",
        "enabled": "0",
        "proto": ["tcp", "udp"],
        "src_dport": "8443",
        "dest_ip": "192.168.1.21",
        "dest_port": "443",
    },
]

TRAFFIC_RULES = [
    {
        ".type": "rule",
        "id": "6",
        "name": "Allow-Ping",
        "enabled": "1",
        "src": "wan",
        "proto": ["icmp"],
        "target": "ACCEPT",
    },
    {
        ".type": "rule",
        "id": "15",
        "name": "Enable_SSH_WAN",
        "enabled": "0",
        "src": "wan",
        "proto": ["tcp"],
        "dest_port": ["22"],
        "target": "ACCEPT",
    },
    {
        ".type": "rule",
        "id": "21",
        "name": "ha-gcs",
        "enabled": "1",
        "src": "wan",
        "proto": ["tcp", "udp"],
        "dest_port": ["9123"],
        "target": "ACCEPT",
    },
    {
        ".type": "rule",
        "id": "45",
        "name": "ha-gcs-ipv4-forward",
        "enabled": "1",
        "src": "wan",
        "dest": "lan",
        "proto": ["tcp", "udp"],
        "dest_port": ["9123"],
        "target": "ACCEPT",
    },
    {
        ".type": "rule",
        "id": "19",
        "name": "Allow-mDNS",
        "enabled": "1",
        "src": "lan",
        "proto": ["udp"],
        "dest_port": ["5353"],
        "target": "ACCEPT",
    },
    {
        ".type": "rule",
        "id": "50",
        "name": "Block-telnet",
        "enabled": "1",
        "src": "wan",
        "proto": ["tcp"],
        "dest_port": ["23"],
        "target": "REJECT",
    },
]

# The answer of /failover/status is a dictionary keyed by interface ID.
# /failover/interfaces/config gives each ID its name and type (a RUTC50 names
# its Wi-Fi interfaces wan2 and wan3 here, with the network names as "name").
FAILOVER_CONFIG = [
    {"id": "mob1s1a1", "name": "mob1s1a1", "enabled": "1", "network_type": "mobile"},
    {"id": "wan2", "name": "wifi4", "enabled": "1", "network_type": "wireless"},
    {"id": "lan", "name": "lan", "enabled": "0", "network_type": "wired"},
]

FAILOVER_STATUS = {
    "mob1s1a1": {
        "enabled": True,
        "score": 6,
        "up": True,
        "age": 2,
        "turn": 1800,
        "online": 3600,
        "uptime": 3610,
        "track_ip": [{"ip": "1.1.1.1", "latency": 0, "packetloss": 0, "status": "up"}],
        "lost": 0,
        "offline": 0,
        "running": True,
        "status": "online",
    },
    "wan2": {
        "enabled": True,
        "score": 0,
        "up": True,
        "age": 6,
        "turn": 9474,
        "online": 0,
        "uptime": 66671,
        "track_ip": [{"ip": "1.1.1.1", "latency": 0, "packetloss": 0, "status": "down"}],
        "lost": 3,
        "offline": 66649,
        "running": True,
        "status": "offline",
    },
    "lan": {"enabled": False, "status": "notracking"},
}

# Two messages in the inbox; the texts are made up.
SMS_MESSAGES = [
    {
        "id": "1",
        "modem_id": "2-1.1",
        "sender": "+491701111111",
        "status": "read",
        "date": "2026-11-17 10:00:00",
        "message": "Data volume used up",
    },
    {
        "id": "2",
        "modem_id": "2-1.1",
        "sender": "Provider",
        "status": "unread",
        "date": "2026-11-18 08:30:00",
        "message": "Welcome",
    },
]

# The firmware the router found at its update server.
FIRMWARE_UPDATES = {
    "device": {
        "version": "RUTC_R_00.07.28.1",
        "size": "11000000",
        "date": "2026-11-10",
        "stable_version": "RUTC_R_00.07.27.1",
        "stable_size": "11000000",
        "stable_date": "2026-11-01",
    }
}

# The firmware download state; the router keeps the last result.
FIRMWARE_PROGRESS = {"percents": "100", "process": "succeeded"}

DATA_LIMIT_STATUS = [
    {
        "id": "mob1s1a1",
        "interface": "mob1s1a1",
        "enabled": "1",
        "data_limit": 10_000_000_000,
        "data_used": "2000000000",
        "due_reset_time": 1796000000,
        "data_warning_enabled": "0",
        "data_warning_limit": 0,
    },
    {"id": "mob1s2a1", "interface": "mob1s2a1", "enabled": "0"},
]


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
        "sim_cards": deepcopy(SIM_CARDS),
        "port_forwards": deepcopy(PORT_FORWARDS),
        "traffic_rules": deepcopy(TRAFFIC_RULES),
        "failover": deepcopy(FAILOVER_STATUS),
        "failover_config": deepcopy(FAILOVER_CONFIG),
        "data_limit": deepcopy(DATA_LIMIT_STATUS),
        "sms": deepcopy(SMS_MESSAGES),
        "firmware_updates": deepcopy(FIRMWARE_UPDATES),
        "firmware_progress": deepcopy(FIRMWARE_PROGRESS),
        "firmware_device": {
            "build_date": "2026-11-06 08:19:47",
            "kernel_version": "6.6.126",
            "version": "RUTC_R_00.07.26.2",
        },
    }
    if wireguard:
        data["interfaces"].append(deepcopy(WIREGUARD_INTERFACE))
    if wifi_metric is not None:
        data["interfaces"][2]["metric"] = wifi_metric
        data["config"][1]["metric"] = str(wifi_metric)
        # A Wi-Fi that is meant to carry the traffic is online for the failover.
        data["failover"]["wan2"]["status"] = "online"
    return data
