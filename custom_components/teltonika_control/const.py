"""Constants for the Teltonika Control integration."""

from __future__ import annotations

DOMAIN = "teltonika_control"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_CONFIG_INTERVAL = "config_interval"
CONF_PROBE_URL = "probe_url"
CONF_VPN_HOST = "vpn_host"
CONF_VPN_PORT = "vpn_port"
CONF_DATA_PLAN = "data_plan_gb"

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
