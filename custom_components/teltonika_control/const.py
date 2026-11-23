"""Constants for the Teltonika Control integration."""

from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "teltonika_control"


@dataclass(frozen=True, slots=True)
class VpnFamily:
    """A VPN type of RutOS that has a configuration and a status page.

    The configuration page says whether an instance is switched on (the field
    is called ``enable`` for OpenVPN and ``enabled`` for the others); the
    status page says what it is doing. WireGuard has its own, richer handling.
    """

    key: str
    label: str
    config_path: str
    status_path: str
    enable_key: str


VPN_FAMILIES: tuple[VpnFamily, ...] = (
    VpnFamily("tailscale", "Tailscale", "/tailscale/config", "/tailscale/status", "enabled"),
    VpnFamily("openvpn", "OpenVPN", "/openvpn/config", "/openvpn/status", "enable"),
    VpnFamily("ipsec", "IPsec", "/ipsec/config", "/ipsec/status", "enabled"),
    VpnFamily("sstp", "SSTP", "/sstp/config", "/sstp/status", "enabled"),
)
VPN_FAMILY = {family.key: family for family in VPN_FAMILIES}

CONF_SCAN_INTERVAL = "scan_interval"
CONF_CONFIG_INTERVAL = "config_interval"
CONF_PROBE_URL = "probe_url"
CONF_VPN_HOST = "vpn_host"
CONF_VPN_PORT = "vpn_port"
CONF_DATA_PLAN = "data_plan_gb"
CONF_TRACKED_DEVICES = "tracked_devices"
CONF_PRESENCE_DELAY = "presence_delay"

# Minutes a tracked device may be missing from the Wi-Fi before it counts as away.
DEFAULT_PRESENCE_DELAY = 1
MAX_PRESENCE_DELAY = 60

DEFAULT_USERNAME = "admin"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 600

# How often the pages that rarely change (configuration, WireGuard instances)
# are read. Actions of the integration read them again at once. A RUTC50 has a
# weak CPU, so the less often the better.
DEFAULT_CONFIG_INTERVAL = 300
MIN_CONFIG_INTERVAL = 30
MAX_CONFIG_INTERVAL = 3600
# The DHCP client list, the failover state and the data limit usage change
# more often than the configuration, but never more rarely than the
# configuration interval allows.
DHCP_INTERVAL = 120
# Seconds to leave a page alone that does not exist or may not be read.
MISSING_PAGE_PAUSE = 300
# GPS readings with 0 satellites in a row that are ignored as glitches.
GPS_GLITCH_POLLS = 3
# Seconds to wait after a roaming change before the setting is read back.
ROAMING_REFRESH_DELAY = 3
# Seconds to wait after a port forward change before the rule is read back.
PORT_FORWARD_REFRESH_DELAY = 2
# After a SIM switch: seconds between two looks at the modem and how long the
# new slot is checked for a SIM before the switch counts as done.
SIM_SWITCH_POLL = 5
SIM_SWITCH_SETTLE = 20
SIM_SWITCH_CHECK_SECONDS = 90

# Returns HTTP 204 with working internet; a captive portal answers with
# a redirect or a login page instead.
DEFAULT_PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
PROBE_TIMEOUT = 6

# Seconds to leave an optional router page alone after it did not answer in
# time, so a struggling router is not kept busy.
SLOW_PAGE_PAUSE = 120

# Tunnel check: a TCP connect to a host behind the VPN. A refused connection
# still proves that the host answered through the tunnel.
DEFAULT_VPN_PORT = 443
VPN_TIMEOUT = 4
# Seconds to wait between switching a WireGuard tunnel off and on, and for the
# router to bring the interface up before the state is read again.
VPN_RECONNECT_DELAY = 3
VPN_REFRESH_DELAY = 4
# How long the firmware download is followed closely after it was started.
FIRMWARE_WATCH_SECONDS = 900
# After "Install firmware": how long the router may take to come back with a
# new version before the installation counts as failed, and how long an answer
# with the same version is accepted as the router not having restarted yet.
FIRMWARE_INSTALL_TIMEOUT = 1800
FIRMWARE_INSTALL_GRACE = 600
# After "Download firmware": seconds until the router's progress page is trusted.
FIRMWARE_DOWNLOAD_SETTLE = 20
# How many of the newest SMS the inbox attribute lists.
SMS_INBOX_SIZE = 10
# States of the firmware update sensor, in the order of the process.
FIRMWARE_STATES = [
    "up_to_date",
    "update_available",
    "downloading",
    "ready",
    "installing",
    "failed",
]

# RutOS wants metrics as strings. The mobile interface usually uses 4, so 0
# makes Wi-Fi win and 10 keeps mobile data in front.
METRIC_WIFI_FIRST = "0"
METRIC_MOBILE_FIRST = "10"

PRIORITY_WIFI_FIRST = "wifi_first"
PRIORITY_MOBILE_FIRST = "mobile_first"

DEFAULT_PORTAL_MINUTES = 10
PORTAL_FIRST_DELAY = 20
PORTAL_POLL_INTERVAL = 15
PRIORITY_VERIFY_DELAY = 25
AP_REFRESH_DELAY = 4

EVENT_PORTAL_RESULT = f"{DOMAIN}_portal_result"
EVENT_SMS_RECEIVED = f"{DOMAIN}_sms_received"

UPLINK_WIFI = "wifi"
UPLINK_MOBILE = "mobile"
UPLINK_ETHERNET = "ethernet"
UPLINK_OTHER = "other"
UPLINK_KINDS = [UPLINK_WIFI, UPLINK_MOBILE, UPLINK_ETHERNET, UPLINK_OTHER]

PORTAL_IDLE = "idle"
PORTAL_NO_WIFI = "no_wifi"
PORTAL_WAITING = "waiting"
PORTAL_LOGIN_REQUIRED = "login_required"
PORTAL_ONLINE = "online"
PORTAL_STATES = [
    PORTAL_IDLE,
    PORTAL_NO_WIFI,
    PORTAL_WAITING,
    PORTAL_LOGIN_REQUIRED,
    PORTAL_ONLINE,
]

BAND_24 = "2.4 GHz"
BAND_5 = "5 GHz"
BAND_6 = "6 GHz"
BANDS = [BAND_24, BAND_5, BAND_6]
