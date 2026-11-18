"""Derive state from raw RutOS API payloads (pure functions, no I/O)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .const import (
    BAND_5,
    BAND_6,
    BAND_24,
    PORTAL_IDLE,
    PORTAL_LOGIN_REQUIRED,
    PORTAL_NO_WIFI,
    PORTAL_ONLINE,
    PORTAL_WAITING,
    UPLINK_ETHERNET,
    UPLINK_MOBILE,
    UPLINK_OTHER,
    UPLINK_WIFI,
    VPN_FAMILIES,
)

WIFI_CLIENT_MODES = ("sta", "multi_ap")
DEFAULT_MOBILE_METRIC = 4
WPA_CONNECTED = "COMPLETED"
# Modem temperatures above this are reported in tenths of a degree.
MAX_PLAUSIBLE_CELSIUS = 150


def to_float(value: Any) -> float | None:
    """Convert numbers and numeric strings, return None for anything else."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def to_int(value: Any, default: int | None = None) -> int | None:
    """Convert to int like :func:`to_float`."""
    number = to_float(value)
    return int(number) if number is not None else default


def _flag(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _first_text(value: Any) -> str | None:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_band(
    *, frequency: Any = None, channel: Any = None, band: Any = None
) -> str | None:
    """Return "2.4 GHz", "5 GHz" or "6 GHz" from whatever the router reports."""
    freq = to_float(frequency)
    if freq:
        if freq < 100:
            freq *= 1000
        if freq < 2600:
            return BAND_24
        if freq < 5900:
            return BAND_5
        return BAND_6

    text = str(band).strip().lower() if band is not None else ""
    if text:
        if text in ("g", "ng", "b", "bg", "11g", "11b", "11ng") or text.startswith("2"):
            return BAND_24
        if text in ("a", "ac", "na", "11a", "11ac") or text.startswith("5"):
            return BAND_5
        if text.startswith("6"):
            return BAND_6

    number = to_int(channel)
    if number:
        return BAND_24 if number <= 14 else BAND_5
    return None


@dataclass(frozen=True, slots=True)
class RouterInfo:
    """Static facts about the router."""

    unique_id: str
    host: str
    name: str
    model: str | None = None
    serial: str | None = None
    mac: str | None = None
    mac_eth: str | None = None
    firmware: str | None = None
    hostname: str | None = None

    @classmethod
    def from_device_status(cls, host: str, data: dict[str, Any]) -> RouterInfo:
        """Build from ``GET /system/device/status``."""
        mnf = data.get("mnfinfo") or {}
        static = data.get("static") or {}
        serial = _first_text(mnf.get("serial"))
        mac = _first_text(mnf.get("mac"))
        mac_eth = _first_text(mnf.get("macEth")) or _first_text(mnf.get("mac_eth"))
        model = _first_text(static.get("device_name")) or _first_text(mnf.get("name"))
        hostname = _first_text(static.get("hostname"))
        return cls(
            unique_id=serial or mac or host,
            host=host,
            name=hostname or model or host,
            model=model,
            serial=serial,
            mac=mac,
            mac_eth=mac_eth,
            firmware=_first_text(static.get("fw_version")),
            hostname=hostname,
        )


@dataclass(frozen=True, slots=True)
class Uplink:
    """The interface that carries the default route."""

    interface_id: str
    name: str
    kind: str
    ip: str | None
    metric: int | None
    # The interface with the best metric that the failover reports as offline,
    # so that it was passed over for this one.
    skipped: str | None = None


@dataclass(frozen=True, slots=True)
class WifiClient:
    """A connected Wi-Fi client (the router acts as station)."""

    config_id: str
    ssid: str | None
    network: str | None
    signal: float | None
    bitrate: float | None
    band: str | None
    channel: int | None


@dataclass(frozen=True, slots=True)
class WifiStation:
    """A saved Wi-Fi client network with its network interface."""

    config_id: str
    ssid: str | None
    network: str | None
    interface_id: str | None
    mode: str


@dataclass(frozen=True, slots=True)
class AccessPoint:
    """An access point of the router itself."""

    config_id: str
    ssid: str | None
    enabled: bool
    radio: str | None
    band: str | None

    @property
    def label(self) -> str:
        """Return a short name such as "WIFI_HYMI 5 GHz"."""
        parts = [self.ssid or self.config_id]
        if self.band:
            parts.append(self.band)
        elif self.radio:
            parts.append(self.radio)
        return " ".join(parts)


def interface_name(interface: dict[str, Any]) -> str:
    """Return the logical name of an interface from ``interfaces/status``."""
    return str(
        interface.get("name") or interface.get("interface") or interface.get("id") or ""
    )


def has_default_route(interface: dict[str, Any]) -> bool:
    """Return whether the interface carries the IPv4 default route."""
    routes = interface.get("route") or []
    return any(
        isinstance(route, dict)
        and route.get("target") == "0.0.0.0"
        and to_int(route.get("mask")) == 0
        for route in routes
    )


def wifi_network_names(wireless_config: Iterable[dict[str, Any]]) -> set[str]:
    """Return the interface names used by saved Wi-Fi client networks."""
    return {
        str(item["network"])
        for item in wireless_config
        if item.get("mode") in WIFI_CLIENT_MODES and item.get("network")
    }


def derive_uplink(
    interfaces: Iterable[dict[str, Any]],
    wifi_networks: set[str],
    offline: set[str] | None = None,
) -> Uplink | None:
    """Pick the default-route interface with the lowest metric.

    The metric only says what the router would like to use. An interface that
    the failover reports as offline (for example a Wi-Fi whose hotspot blocks
    the check pings) does not carry traffic, so the best interface that is not
    offline wins. If every interface is offline the metric alone decides.
    """
    offline = offline or set()
    candidates = [i for i in interfaces if has_default_route(i)]
    if not candidates:
        return None

    def lowest(items: list[dict[str, Any]]) -> dict[str, Any]:
        return min(items, key=lambda item: to_int(item.get("metric"), 99))

    def is_offline(item: dict[str, Any]) -> bool:
        return interface_name(item) in offline or str(item.get("id", "")) in offline

    best = lowest(candidates)
    skipped: str | None = None
    working = [i for i in candidates if not is_offline(i)]
    if working and is_offline(best):
        skipped = interface_name(best)
        best = lowest(working)

    name = interface_name(best)
    if name in wifi_networks:
        kind = UPLINK_WIFI
    elif name.startswith("mob") or str(best.get("id", "")).startswith("mob"):
        kind = UPLINK_MOBILE
    elif str(best.get("type") or best.get("typename") or "").lower() == "ethernet" or (
        name.lower().startswith(("wan", "eth", "lan"))
    ):
        kind = UPLINK_ETHERNET
    else:
        kind = UPLINK_OTHER

    ips = best.get("ipaddrs") or []
    ip = str(ips[0]).split("/")[0] if ips else None
    return Uplink(
        interface_id=str(best.get("id") or name),
        name=name,
        kind=kind,
        ip=ip,
        metric=to_int(best.get("metric")),
        skipped=skipped,
    )


def radio_band(radio: str | None, wireless_devices: Iterable[dict[str, Any]]) -> str | None:
    if not radio:
        return None
    for device in wireless_devices:
        if device.get("id") == radio or device.get("name") == radio:
            return normalize_band(
                frequency=device.get("frequency"),
                channel=device.get("channel"),
                band=device.get("band"),
            )
    return None


def _network_of(row: dict[str, Any], configs: dict[str, dict[str, Any]]) -> str | None:
    config = configs.get(str(row.get("id")), {})
    network = config.get("network") or row.get("network")
    return str(network) if network else None


def derive_wifi_client(
    wireless_status: Iterable[dict[str, Any]],
    wireless_config: Iterable[dict[str, Any]],
    wireless_devices: Iterable[dict[str, Any]],
    uplink_network: str | None = None,
) -> WifiClient | None:
    """Return the connected Wi-Fi client, if the router is one.

    A router can be connected twice to the same network (for example a 2.4 GHz
    client and a 5 GHz Multi AP entry). The connection that carries the uplink
    wins; without an uplink match the first connected one is used.
    """
    configs = {str(item.get("id")): item for item in wireless_config}
    devices = list(wireless_devices)
    rows = sorted(
        wireless_status,
        key=lambda row: (
            uplink_network is None or _network_of(row, configs) != uplink_network
        ),
    )
    for row in rows:
        if (
            row.get("mode") not in WIFI_CLIENT_MODES
            or row.get("wpa_state") != WPA_CONNECTED
        ):
            continue
        config_id = str(row.get("id"))
        config = configs.get(config_id, {})
        radio = _first_text(config.get("device"))
        band = normalize_band(
            frequency=row.get("freq") or row.get("frequency"),
            channel=row.get("channel"),
            band=row.get("band"),
        ) or radio_band(radio, devices)

        bitrate = to_float(row.get("bitrate"))
        if bitrate is not None:
            if bitrate >= 1_000_000:
                bitrate /= 1_000_000
            elif bitrate >= 1_000:
                bitrate /= 1_000
            bitrate = round(bitrate)

        return WifiClient(
            config_id=config_id,
            ssid=config.get("ssid") or row.get("ssid"),
            network=config.get("network") or row.get("network"),
            signal=to_float(row.get("signal")),
            bitrate=bitrate,
            band=band,
            channel=to_int(row.get("channel")),
        )
    # Without a connected status row (the Wi-Fi status page can be slow or
    # missing), an uplink on a Wi-Fi interface still tells which saved network
    # it is. Signal and speed stay unknown.
    if uplink_network:
        for config_id, config in configs.items():
            if (
                config.get("mode") in WIFI_CLIENT_MODES
                and config.get("network") == uplink_network
            ):
                return WifiClient(
                    config_id=config_id,
                    ssid=config.get("ssid"),
                    network=uplink_network,
                    signal=None,
                    bitrate=None,
                    band=radio_band(_first_text(config.get("device")), devices),
                    channel=None,
                )
    return None


def derive_stations(
    wireless_config: Iterable[dict[str, Any]], interfaces: Iterable[dict[str, Any]]
) -> list[WifiStation]:
    """Return saved Wi-Fi client networks and the interface behind each."""
    interface_ids = {interface_name(i): str(i.get("id")) for i in interfaces}
    stations: list[WifiStation] = []
    for item in wireless_config:
        if item.get("mode") not in WIFI_CLIENT_MODES:
            continue
        network = item.get("network")
        stations.append(
            WifiStation(
                config_id=str(item.get("id")),
                ssid=item.get("ssid"),
                network=network,
                interface_id=interface_ids.get(str(network)) if network else None,
                mode=str(item.get("mode")),
            )
        )
    return stations


def radio_occupant(
    wireless_config: Iterable[dict[str, Any]], radio: str
) -> dict[str, Any] | None:
    """Return the Wi-Fi client or Multi AP entry that already uses a radio.

    The router allows only one client or one Multi AP per radio.
    """
    for item in wireless_config:
        if item.get("mode") not in WIFI_CLIENT_MODES:
            continue
        devices = item.get("device")
        if isinstance(devices, str):
            devices = [devices]
        if radio in (devices or []):
            return item
    return None


def next_multi_ap_priority(entries: Iterable[dict[str, Any]]) -> int:
    """Return a priority that puts a new Multi AP entry last."""
    return max([0, *(to_int(e.get("priority"), 0) or 0 for e in entries)]) + 1


# Default interfaces of the router; only interfaces created for a Wi-Fi client
# may be removed together with the saved network.
PROTECTED_INTERFACE_IDS = frozenset(
    {"lan", "lan1", "lan2", "wan", "wan1", "wan2", "wan6", "loopback"}
)
PROTECTED_INTERFACE_PREFIXES = ("mob", "vpn")


def is_protected_interface(interface_id: str) -> bool:
    """Return whether an interface belongs to the router's default setup."""
    lowered = interface_id.lower()
    return lowered in PROTECTED_INTERFACE_IDS or lowered.startswith(
        PROTECTED_INTERFACE_PREFIXES
    )


def derive_wifi_first(
    interfaces: Iterable[dict[str, Any]],
    interface_config: Iterable[dict[str, Any]],
    wifi_networks: set[str],
) -> bool | None:
    """Return whether a Wi-Fi interface has a better metric than mobile data."""
    config = list(interface_config)
    wifi_ids = [
        str(i.get("id"))
        for i in interfaces
        if interface_name(i) in wifi_networks and i.get("id")
    ]
    if not wifi_ids:
        return None

    mobile_metrics = [
        to_int(c.get("metric"), DEFAULT_MOBILE_METRIC)
        for c in config
        if str(c.get("id", "")).startswith("mob")
    ]
    mobile = min(mobile_metrics) if mobile_metrics else DEFAULT_MOBILE_METRIC
    wifi_metrics = [
        to_int(c.get("metric"), 99) for c in config if str(c.get("id")) in wifi_ids
    ]
    return any(metric < mobile for metric in wifi_metrics)


def derive_access_points(
    wireless_config: Iterable[dict[str, Any]],
    wireless_status: Iterable[dict[str, Any]],
    wireless_devices: Iterable[dict[str, Any]],
) -> list[AccessPoint]:
    """Return the router's own access points with their real on/off state."""
    status_rows = {str(row.get("id")): row for row in wireless_status}
    devices = list(wireless_devices)
    points: list[AccessPoint] = []
    for item in wireless_config:
        if item.get("mode") != "ap":
            continue
        config_id = str(item.get("id"))
        radio = _first_text(item.get("device"))
        row = status_rows.get(config_id, {})
        band = (
            normalize_band(
                frequency=row.get("freq") or row.get("frequency"),
                channel=row.get("channel"),
                band=row.get("band"),
            )
            or radio_band(radio, devices)
        )
        enabled = _flag(item.get("enabled"), not _flag(item.get("disabled"), False))
        points.append(
            AccessPoint(
                config_id=config_id,
                ssid=item.get("ssid"),
                enabled=enabled,
                radio=radio,
                band=band,
            )
        )
    return points


def is_modem_online(modem: dict[str, Any]) -> bool:
    """Return whether ``modems/status`` returned the full status."""
    return modem.get("simstate") is not None or modem.get("conntype") is not None


def modem_temperature(modem: dict[str, Any]) -> float | None:
    """Return the modem temperature in °C."""
    value = to_float(modem.get("temperature"))
    if value is None:
        return None
    return value / 10 if abs(value) > MAX_PLAUSIBLE_CELSIUS else value


def modem_registration(modem: dict[str, Any]) -> str | None:
    """Return the network registration text, for example "Registered, home"."""
    return _first_text(modem.get("operator_state") or modem.get("netstate"))


def modem_is_roaming(modem: dict[str, Any]) -> bool | None:
    """Return whether the modem is registered in a foreign network.

    None while the router reports no registration text.
    """
    text = modem_registration(modem)
    if text is None:
        return None
    return "roaming" in text.lower()


def derive_portal_state(
    *,
    waiting: bool,
    wifi_client: WifiClient | None,
    uplink: Uplink | None,
    internet: bool | None,
    wifi_failed: bool = False,
) -> str:
    """Return the captive portal state shown on the dashboard.

    ``wifi_failed`` is true when the router's failover calls every Wi-Fi
    interface offline. A hotspot whose login has expired fails that check while
    the traffic goes over mobile data, so the internet check of Home Assistant
    still passes and cannot show it.
    """
    if waiting:
        return PORTAL_WAITING
    wifi_is_uplink = uplink is not None and uplink.kind == UPLINK_WIFI
    # The Wi-Fi status page can be slow or missing while the Wi-Fi interface
    # clearly carries the default route, so that counts as connected too.
    if wifi_client is None and not wifi_is_uplink:
        return PORTAL_NO_WIFI
    if wifi_failed:
        return PORTAL_LOGIN_REQUIRED
    if wifi_is_uplink:
        if internet is False:
            return PORTAL_LOGIN_REQUIRED
        if internet:
            return PORTAL_ONLINE
    return PORTAL_IDLE


@dataclass(frozen=True, slots=True)
class SavedNetwork:
    """A Wi-Fi network saved on the router, as client or in the Multi AP list."""

    label: str
    ssid: str
    kind: str
    config_id: str | None
    band: str | None


SAVED_CLIENT = "client"
SAVED_MULTI_AP = "multi_ap"


def derive_saved_networks(
    wireless_config: Iterable[dict[str, Any]],
    multi_ap: Iterable[dict[str, Any]],
    wireless_devices: Iterable[dict[str, Any]],
) -> list[SavedNetwork]:
    """Return the saved Wi-Fi client networks and the Multi AP list entries."""
    configs = list(wireless_config)
    devices = list(wireless_devices)
    saved: list[SavedNetwork] = []
    for item in configs:
        ssid = item.get("ssid")
        if item.get("mode") != "sta" or not ssid:
            continue
        band = radio_band(_first_text(item.get("device")), devices)
        label = f"{ssid} ({band})" if band else str(ssid)
        saved.append(SavedNetwork(label, str(ssid), SAVED_CLIENT, str(item.get("id")), band))

    multi_band = next(
        (
            radio_band(_first_text(item.get("device")), devices)
            for item in configs
            if item.get("mode") == "multi_ap"
        ),
        None,
    )
    for entry in multi_ap:
        ssid = entry.get("ssid")
        if not ssid:
            continue
        detail = f"{multi_band}, Multi AP" if multi_band else "Multi AP"
        saved.append(
            SavedNetwork(f"{ssid} ({detail})", str(ssid), SAVED_MULTI_AP, None, multi_band)
        )
    return saved


@dataclass(frozen=True, slots=True)
class ScanNetwork:
    """A network found by a scan, ready to be saved."""

    label: str
    ssid: str
    bssid: str | None
    radio: str
    band: str | None
    signal: float | None
    encrypted: bool


def build_scan_networks(
    results: Iterable[dict[str, Any]], saved: Iterable[SavedNetwork]
) -> tuple[list[ScanNetwork], int, int]:
    """Return the new networks, how many were seen and how many were hidden.

    The same SSID is listed once per band with its best signal. Networks that
    are already saved in the same band are hidden.
    """
    saved_keys = {(item.ssid, item.band) for item in saved}
    best: dict[tuple[str, str | None], dict[str, Any]] = {}
    for item in results:
        ssid = item.get("ssid")
        if not ssid:
            continue
        key = (str(ssid), item.get("band"))
        signal = to_float(item.get("signal"))
        current = best.get(key)
        if current is None or (signal or -999) > (to_float(current.get("signal")) or -999):
            best[key] = item

    networks: list[ScanNetwork] = []
    for (ssid, band), item in best.items():
        if (ssid, band) in saved_keys:
            continue
        signal = to_float(item.get("signal"))
        encrypted = bool(item.get("encrypted"))
        parts = [band or str(item.get("radio")), "secured" if encrypted else "open"]
        if signal is not None:
            parts.append(f"{signal:.0f} dBm")
        networks.append(
            ScanNetwork(
                label=f"{ssid} [{' · '.join(parts)}]",
                ssid=ssid,
                bssid=item.get("bssid"),
                radio=str(item.get("radio")),
                band=band,
                signal=signal,
                encrypted=encrypted,
            )
        )
    networks.sort(key=lambda n: n.signal if n.signal is not None else -999, reverse=True)
    return networks, len(best), len(best) - len(networks)


@dataclass(frozen=True, slots=True)
class GpsPosition:
    """A GPS fix of the router."""

    latitude: float
    longitude: float
    altitude: float | None
    speed: float | None
    accuracy: float | None
    satellites: int | None
    heading: float | None
    fix_status: str | None


def _first_present(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if raw.get(key) is not None:
            return raw[key]
    return None


def derive_gps(raw: dict[str, Any] | None) -> GpsPosition | None:
    """Return the position from ``gps/position/status``, None without a fix.

    The router sends every value as a string and reports zeros while it has
    no fix, so such a position is not trusted.
    """
    if not isinstance(raw, dict):
        return None
    latitude = to_float(raw.get("latitude"))
    longitude = to_float(raw.get("longitude"))
    if latitude is None or longitude is None:
        return None
    if (latitude == 0 and longitude == 0) or abs(latitude) > 90 or abs(longitude) > 180:
        return None
    return GpsPosition(
        latitude=latitude,
        longitude=longitude,
        altitude=to_float(raw.get("altitude")),
        speed=to_float(raw.get("speed")),
        accuracy=to_float(raw.get("accuracy")),
        satellites=to_int(raw.get("satellites")),
        heading=to_float(_first_present(raw, "angle", "heading", "course")),
        fix_status=_first_text(raw.get("fix_status")),
    )


@dataclass(frozen=True, slots=True)
class SystemUsage:
    """Uptime, load and memory of the router."""

    uptime: int | None
    cpu_load: float | None
    ram_usage: float | None
    flash_usage: float | None
    router_time: datetime | None


def derive_system_usage(raw: Any) -> SystemUsage | None:
    """Read ``/system/device/usage/status``; None if the router has none."""
    if not isinstance(raw, dict) or not raw:
        return None
    memory = raw.get("memory") if isinstance(raw.get("memory"), dict) else {}
    load = to_float(raw.get("loadavg"))
    stamp = to_float(raw.get("localtime"))
    return SystemUsage(
        uptime=to_int(raw.get("uptime_seconds")),
        cpu_load=round(load * 100, 1) if load is not None else None,
        ram_usage=to_float(memory.get("ram_percentage")),
        flash_usage=to_float(memory.get("flash_percentage")),
        router_time=datetime.fromtimestamp(stamp, UTC) if stamp else None,
    )


VPN_PROTOCOLS = ("wireguard",)


@dataclass(frozen=True, slots=True)
class VpnTunnel:
    """One VPN tunnel interface of the router."""

    tunnel_id: str
    protocol: str
    up: bool | None
    rx_bytes: int | None
    tx_bytes: int | None
    uptime: int | None
    # None when the router gave no configuration (missing rights): the
    # tunnel can be watched but not switched.
    enabled: bool | None


def derive_vpn_tunnels(
    interfaces: Iterable[dict[str, Any]], wireguard_config: Iterable[dict[str, Any]]
) -> list[VpnTunnel]:
    """Combine the interface state and the configuration of WireGuard tunnels."""
    configs = {
        str(item["id"]): item for item in wireguard_config if item.get("id")
    }
    tunnels: dict[str, VpnTunnel] = {}
    for interface in interfaces:
        protocol = str(interface.get("proto") or "").lower()
        tunnel_id = str(interface.get("id") or "")
        if protocol not in VPN_PROTOCOLS or not tunnel_id:
            continue
        config = configs.get(tunnel_id)
        up = interface.get("up", interface.get("is_up"))
        tunnels[tunnel_id] = VpnTunnel(
            tunnel_id=tunnel_id,
            protocol=protocol,
            up=up if isinstance(up, bool) else None,
            rx_bytes=to_int(interface.get("rx_bytes")),
            tx_bytes=to_int(interface.get("tx_bytes")),
            uptime=to_int(interface.get("uptime")),
            enabled=_flag(config.get("enabled"), True) if config else None,
        )
    for tunnel_id, config in configs.items():
        if tunnel_id not in tunnels:
            # A disabled instance has no interface.
            tunnels[tunnel_id] = VpnTunnel(
                tunnel_id=tunnel_id,
                protocol="wireguard",
                up=False,
                rx_bytes=None,
                tx_bytes=None,
                uptime=None,
                enabled=_flag(config.get("enabled"), True),
            )
    return sorted(tunnels.values(), key=lambda tunnel: tunnel.tunnel_id)


_VPN_UP_WORDS = frozenset(
    {"connected", "up", "running", "online", "established", "active", "ok", "started"}
)
_VPN_DOWN_WORDS = frozenset(
    {
        "not",
        "disconnected",
        "down",
        "stopped",
        "offline",
        "inactive",
        "disabled",
        "failed",
        "error",
        "needslogin",
        "needsmachineauth",
    }
)
_WORD = re.compile(r"[a-z]+")


def vpn_status_connected(text: Any) -> bool | None:
    """Read a VPN status text; None when it is neither clearly up nor down.

    The wording differs per VPN type, so it is matched by words: "Running",
    "Connected" and "Established" are up, "Stopped", "Disconnected" and
    "NeedsLogin" are down, "Connecting" says nothing yet.
    """
    if isinstance(text, bool):
        return text
    if not isinstance(text, str):
        return None
    words = set(_WORD.findall(text.lower()))
    if words & _VPN_DOWN_WORDS:
        return False
    if words & _VPN_UP_WORDS:
        return True
    return None


@dataclass(frozen=True, slots=True)
class VpnInstance:
    """One instance of Tailscale, OpenVPN, IPsec or SSTP."""

    family: str
    instance_id: str
    label: str
    # None when the router gave no enable flag: the instance cannot be switched.
    enabled: bool | None
    # None when the router gave no status or the text is not understood.
    connected: bool | None
    status: str | None
    details: dict[str, Any]


def _vpn_status_rows(
    config_ids: list[str], names: dict[str, str], status: Any
) -> dict[str, dict[str, Any]]:
    """Map instance id to its status row from the shapes the router uses."""
    rows: dict[str, dict[str, Any]] = {}
    if isinstance(status, dict):
        if status and all(isinstance(value, dict) for value in status.values()):
            rows = {str(key): value for key, value in status.items()}
        elif status and len(config_ids) == 1:
            rows = {config_ids[0]: status}
    elif isinstance(status, list):
        items = [item for item in status if isinstance(item, dict)]
        if items and all(item.get("id") is not None for item in items):
            rows = {str(item["id"]): item for item in items}
        elif len(items) == len(config_ids):
            # Tailscale reports no id: the rows follow the order of the config.
            rows = dict(zip(config_ids, items, strict=True))
    # IPsec keys its status by instance name.
    for instance_id, name in names.items():
        if instance_id not in rows and name in rows:
            rows[instance_id] = rows[name]
    return rows


def _vpn_details(row: dict[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for key in ("uptime", "rx", "tx", "clients_connected"):
        number = to_int(row.get(key))
        if number is not None:
            details[key] = number
    version = _first_text(row.get("version"))
    if version:
        details["version"] = version
    peers = row.get("peers")
    if isinstance(peers, dict):
        for source, target in (("online", "peers_online"), ("total", "peers_total")):
            number = to_int(peers.get(source))
            if number is not None:
                details[target] = number
    return details


def derive_vpn_instances(
    family: str,
    label: str,
    enable_key: str,
    config: Iterable[dict[str, Any]] | None,
    status: Any,
) -> list[VpnInstance]:
    """Combine the configuration and the status of one VPN type.

    Instances come from the configuration; without it nothing can be switched.
    A status of None means the page is not available.
    """
    configs = [item for item in config or [] if isinstance(item, dict) and item.get("id")]
    config_ids = [str(item["id"]) for item in configs]
    names = {str(item["id"]): str(item["name"]) for item in configs if item.get("name")}
    rows = _vpn_status_rows(config_ids, names, status)
    instances: list[VpnInstance] = []
    for item in configs:
        instance_id = str(item["id"])
        enabled = _flag(item.get(enable_key), False) if enable_key in item else None
        row = rows.get(instance_id)
        text = _first_text(row.get("status", row.get("state"))) if row else None
        if enabled is False:
            connected: bool | None = False
        elif row:
            connected = vpn_status_connected(row.get("status", row.get("state")))
        else:
            connected = False if status is not None else None
        name = names.get(instance_id)
        if name is None and len(configs) > 1:
            name = instance_id
        if name is None or name.lower() in (family, label.lower()):
            shown = label
        else:
            shown = f"{label} {name}"
        instances.append(
            VpnInstance(
                family=family,
                instance_id=instance_id,
                label=shown,
                enabled=enabled,
                connected=connected,
                status=text,
                details=_vpn_details(row) if row else {},
            )
        )
    return instances


@dataclass(frozen=True, slots=True)
class SimCard:
    """The roaming setting of one SIM slot (``/sim_cards/config``)."""

    card_id: str
    modem_id: str | None
    slot: int | None
    roaming_allowed: bool | None


def derive_sim_cards(raw: Iterable[dict[str, Any]] | None) -> list[SimCard]:
    """Read the SIM settings; the router stores ``deny_roaming`` as "0" or "1"."""
    cards: list[SimCard] = []
    for item in raw or []:
        card_id = str(item.get("id") or "")
        if not card_id:
            continue
        deny = item.get("deny_roaming")
        cards.append(
            SimCard(
                card_id=card_id,
                modem_id=_first_text(item.get("modem")),
                slot=to_int(item.get("position")),
                roaming_allowed=None if deny is None else not _flag(deny, False),
            )
        )
    return sorted(cards, key=lambda card: (card.modem_id or "", card.slot or 0))


@dataclass(frozen=True, slots=True)
class FailoverInterface:
    """The failover (mwan3) state of one uplink interface."""

    interface_id: str
    label: str
    # One of the UPLINK_* kinds, taken from the failover configuration.
    kind: str
    status: str | None
    online: bool | None
    score: float | None
    age: int | None
    # The router counts seconds online and offline, and tracking probes lost.
    seconds_online: int | None
    seconds_offline: int | None
    lost: int | None
    # The interface name from the failover configuration (``wifi4``).
    name: str = ""


# The router names the kind of each failover interface in its configuration.
FAILOVER_NETWORK_TYPES = {
    "mobile": UPLINK_MOBILE,
    "wireless": UPLINK_WIFI,
    "wired": UPLINK_ETHERNET,
}
FAILOVER_KIND_LABELS = {
    UPLINK_MOBILE: "Mobile",
    UPLINK_WIFI: "Wi-Fi",
    UPLINK_ETHERNET: "Ethernet",
}


def failover_kind(
    interface_id: str,
    name: str,
    network_type: str | None,
    wifi_networks: set[str],
) -> str:
    """Tell what an interface is, from the router's own data.

    The failover configuration says ``mobile``, ``wireless`` or ``wired``. If it
    does not (an unknown value or no configuration row), the Wi-Fi networks of
    the wireless configuration and the ``mob`` prefix of mobile interfaces
    decide.
    """
    kind = FAILOVER_NETWORK_TYPES.get((network_type or "").strip().lower())
    if kind:
        return kind
    if interface_id in wifi_networks or name in wifi_networks:
        return UPLINK_WIFI
    if interface_id.startswith("mob") or name.startswith("mob"):
        return UPLINK_MOBILE
    return UPLINK_OTHER


def _failover_online(status: str) -> bool | None:
    """Tell from the router's status text whether the check passes.

    ``standby`` is a working interface that is not in use at the moment (the
    router keeps it ready as a backup), so it counts as online. ``starting``
    and ``notracking`` say nothing yet.
    """
    text = status.strip().lower()
    if text in ("online", "standby"):
        return True
    if text == "offline":
        return False
    return None


def derive_failover(
    raw: Any,
    config: Iterable[dict[str, Any]] | None = None,
    wifi_networks: set[str] | None = None,
) -> list[FailoverInterface]:
    """Read ``/failover/status``: a dictionary with one entry per interface.

    The keys of the status are interface IDs (``wan2``). The failover
    configuration gives each one a name (the interface name of the Wi-Fi
    network, ``wifi4``) and a type. Interfaces that are not enabled for
    failover are skipped.
    """
    if not isinstance(raw, dict):
        return []
    networks = wifi_networks or set()
    rows = {str(row["id"]): row for row in config or [] if row.get("id")}
    interfaces: list[FailoverInterface] = []
    for interface_id, item in raw.items():
        if (
            not isinstance(item, dict)
            or not interface_id
            or not _flag(item.get("enabled"), True)
        ):
            continue
        interface_id = str(interface_id)
        row = rows.get(interface_id, {})
        name = str(row.get("name") or interface_id)
        kind = failover_kind(interface_id, name, row.get("network_type"), networks)
        prefix = FAILOVER_KIND_LABELS.get(kind)
        status = str(item["status"]).strip() if item.get("status") is not None else ""
        interfaces.append(
            FailoverInterface(
                interface_id=interface_id,
                label=f"{prefix} ({name})" if prefix else name,
                kind=kind,
                status=status or None,
                online=_failover_online(status),
                score=to_float(item.get("score")),
                age=to_int(item.get("age")),
                seconds_online=to_int(item.get("online")),
                seconds_offline=to_int(item.get("offline")),
                lost=to_int(item.get("lost")),
                name=name,
            )
        )
    return sorted(interfaces, key=lambda interface: interface.interface_id)


@dataclass(frozen=True, slots=True)
class DataLimit:
    """The data limit of one mobile interface and how much of it is used."""

    interface_id: str
    label: str
    used: float | None
    limit: float | None
    resets_at: datetime | None

    @property
    def used_percent(self) -> float | None:
        """Return the used part of the limit in percent."""
        if self.used is None or not self.limit:
            return None
        return round(self.used / self.limit * 100, 1)

    @property
    def reached(self) -> bool | None:
        """Return whether the limit is used up."""
        if self.used is None or not self.limit:
            return None
        return self.used >= self.limit


def derive_data_limits(
    raw: Iterable[dict[str, Any]] | None,
    interface_config: Iterable[dict[str, Any]],
    plan_bytes: float | None = None,
) -> list[DataLimit]:
    """Read ``/data_limit/status``; only interfaces with an enabled limit count.

    The router names the SIM slot of an interface in ``interfaces/config``. With
    a data plan the limit is the plan, not the router's own limit: the router
    only keeps the count, and what the provider does when the plan is used up
    (usually slowing the connection down) is not the router's business.
    """
    slots = {
        str(item["id"]): to_int(item.get("sim"))
        for item in interface_config
        if item.get("id")
    }
    limits: list[DataLimit] = []
    for item in raw or []:
        interface_id = str(item.get("interface") or item.get("id") or "")
        router_limit = to_float(item.get("data_limit"))
        if not interface_id or not _flag(item.get("enabled"), False) or not router_limit:
            continue
        slot = slots.get(interface_id)
        reset = to_float(item.get("due_reset_time"))
        limits.append(
            DataLimit(
                interface_id=interface_id,
                label=f"SIM {slot}" if slot else interface_id,
                used=to_float(item.get("data_used")),
                limit=plan_bytes if plan_bytes and plan_bytes > 0 else router_limit,
                resets_at=datetime.fromtimestamp(reset, UTC) if reset else None,
            )
        )
    return sorted(limits, key=lambda item: item.interface_id)


@dataclass(frozen=True, slots=True)
class PortForward:
    """One port forwarding rule of the firewall."""

    rule_id: str
    name: str
    enabled: bool
    protocol: str | None
    external_port: str | None
    internal_port: str | None


def _joined(value: Any) -> str | None:
    if isinstance(value, (list, tuple)):
        text = ", ".join(str(part) for part in value)
    else:
        text = str(value) if value is not None else ""
    return text.strip() or None


def derive_port_forwards(raw: Iterable[dict[str, Any]] | None) -> list[PortForward]:
    """Read ``/firewall/port_forwards/config``; a rule without the flag is on."""
    rules: list[PortForward] = []
    for item in raw or []:
        rule_id = str(item.get("id") or "")
        if not rule_id:
            continue
        rules.append(
            PortForward(
                rule_id=rule_id,
                name=str(item.get("name") or "").strip() or rule_id,
                enabled=_flag(item.get("enabled"), True),
                protocol=_joined(item.get("proto")),
                external_port=_joined(item.get("src_dport")),
                internal_port=_joined(item.get("dest_port")),
            )
        )
    return sorted(rules, key=lambda rule: rule.rule_id)


# The router's own rules are named "Allow-...". Rules are sorted into groups so
# that a dashboard can show the ones that let the internet in, and a rule that
# the router needs for itself is not switched off by accident.
TRAFFIC_GROUP_SYSTEM = "system"
TRAFFIC_GROUP_ACCESS = "access"
TRAFFIC_GROUP_FORWARD = "forward"
TRAFFIC_GROUP_OTHER = "other"
SYSTEM_RULE_PREFIX = "Allow-"
# Zones that are the inside of the router; rules from them do not let the
# internet in.
INSIDE_ZONES = {"lan"}


@dataclass(frozen=True, slots=True)
class TrafficRule:
    """One traffic rule of the firewall."""

    rule_id: str
    name: str
    enabled: bool
    source: str | None
    destination: str | None
    protocol: str | None
    ports: str | None
    action: str | None
    group: str

    @property
    def opens_internet(self) -> bool:
        """Return whether the rule is on and lets outside traffic in."""
        return self.enabled and self.group in (TRAFFIC_GROUP_ACCESS, TRAFFIC_GROUP_FORWARD)


def traffic_rule_group(
    name: str, source: str | None, destination: str | None, action: str | None
) -> str:
    """Sort a traffic rule: router rule, access to the router, forward or other."""
    if name.startswith(SYSTEM_RULE_PREFIX):
        return TRAFFIC_GROUP_SYSTEM
    if (action or "").upper() != "ACCEPT" or not source or source in INSIDE_ZONES:
        return TRAFFIC_GROUP_OTHER
    return TRAFFIC_GROUP_FORWARD if destination else TRAFFIC_GROUP_ACCESS


def derive_traffic_rules(raw: Iterable[dict[str, Any]] | None) -> list[TrafficRule]:
    """Read ``/firewall/traffic_rules/config``; a rule without the flag is on."""
    rules: list[TrafficRule] = []
    for item in raw or []:
        rule_id = str(item.get("id") or "")
        if not rule_id:
            continue
        name = str(item.get("name") or "").strip() or rule_id
        source = _joined(item.get("src"))
        destination = _joined(item.get("dest"))
        action = _joined(item.get("target"))
        rules.append(
            TrafficRule(
                rule_id=rule_id,
                name=name,
                enabled=_flag(item.get("enabled"), True),
                source=source,
                destination=destination,
                protocol=_joined(item.get("proto")),
                ports=_joined(item.get("dest_port")),
                action=action,
                group=traffic_rule_group(name, source, destination, action),
            )
        )
    return sorted(rules, key=lambda rule: (to_int(rule.rule_id, 10**6) or 0, rule.rule_id))


PHONE_NUMBER_HINT = "Enter the phone number in digits, with a leading + for a country code"
_PHONE_NUMBER = re.compile(r"^\+?\d{3,20}$")


def clean_phone_number(value: str) -> str | None:
    """Drop the separators people type; None when digits are left that are no number."""
    text = re.sub(r"[\s\-()./]", "", value)
    return text if _PHONE_NUMBER.match(text) else None


@dataclass(frozen=True, slots=True)
class SmsMessage:
    """One SMS stored on the router."""

    key: str
    message_id: str
    modem_id: str
    sender: str
    status: str | None
    date: str | None
    message: str


def derive_sms(raw: Iterable[dict[str, Any]] | None) -> list[SmsMessage] | None:
    """Read ``/messages/status``; None means the router has no SMS page.

    The message ids can repeat after messages were deleted, so the key also
    contains the sender and the date.
    """
    if raw is None:
        return None
    messages: list[SmsMessage] = []
    for item in raw:
        message_id = str(item.get("id") or "").strip()
        if not message_id:
            continue
        modem_id = str(item.get("modem_id") or "").strip()
        sender = str(item.get("sender") or "").strip()
        date = _first_text(item.get("date"))
        messages.append(
            SmsMessage(
                key=f"{modem_id}|{message_id}|{sender}|{date}",
                message_id=message_id,
                modem_id=modem_id,
                sender=sender,
                status=_first_text(item.get("status")),
                date=date,
                message=str(item.get("message") or ""),
            )
        )
    return messages


@dataclass(frozen=True, slots=True)
class FirmwareDownload:
    """The state of the firmware download (``/firmware/device/progress/status``)."""

    process: str | None
    percent: int | None

    @property
    def ready(self) -> bool:
        """Return whether a complete firmware file is waiting to be installed."""
        text = (self.process or "").lower()
        return self.percent == 100 and text in _DOWNLOAD_DONE


_DOWNLOAD_DONE = frozenset({"succeeded", "success", "done", "finished", "completed", "ready"})


def derive_installed_firmware(raw: Any) -> str | None:
    """Read the running firmware version from ``/firmware/device/status``."""
    return _first_text(raw.get("version")) if isinstance(raw, dict) else None


def derive_firmware_download(raw: Any) -> FirmwareDownload | None:
    """Read the download progress; None when the router gives no such page."""
    if not isinstance(raw, dict):
        return None
    process = _first_text(raw.get("process"))
    percent = to_int(raw.get("percents", raw.get("percent")))
    if process is None and percent is None:
        return None
    return FirmwareDownload(process=process, percent=percent)


@dataclass(frozen=True, slots=True)
class FirmwareInfo:
    """The installed firmware and the newest one the router found."""

    installed: str | None
    latest: str
    # The newest version, stable or not, as the update server lists them.
    newest: str | None
    update_available: bool | None


_VERSION_PART = re.compile(r"\d+(?:\.\d+)+")


def firmware_version_tuple(text: str | None) -> tuple[int, ...] | None:
    """Turn ``RUTC50_R_00.07.25.2`` or ``7.25.2`` into ``(7, 25, 2)``.

    The router names a release with a leading ``00`` major, and the update
    server may use either form, so both are reduced to the same numbers.
    """
    if not text:
        return None
    parts = _VERSION_PART.findall(text)
    if not parts:
        return None
    numbers = tuple(int(part) for part in parts[-1].split("."))
    if len(numbers) > 2 and numbers[0] == 0:
        numbers = numbers[1:]
    return numbers


def derive_firmware(installed: str | None, raw: Any) -> FirmwareInfo | None:
    """Read ``/firmware/device/updates/status``; None without update information.

    The stable release is preferred over the newest one when it is a real
    version. Whether an update is available is only said when both versions
    can be compared.
    """
    device = raw.get("device") if isinstance(raw, dict) else None
    if not isinstance(device, dict):
        return None
    stable = _first_text(device.get("stable_version"))
    newest = _first_text(device.get("version"))
    # A router without a stable channel reports a placeholder such as "newest".
    latest = stable if firmware_version_tuple(stable) is not None else (newest or stable)
    if latest is None:
        return None
    have = firmware_version_tuple(installed)
    offered = firmware_version_tuple(latest)
    available = offered > have if have is not None and offered is not None else None
    return FirmwareInfo(
        installed=installed,
        latest=latest,
        newest=newest,
        update_available=available,
    )


@dataclass(slots=True)
class TeltonikaData:
    """One snapshot of the router state."""

    interfaces: list[dict[str, Any]] = field(default_factory=list)
    interface_config: list[dict[str, Any]] = field(default_factory=list)
    wireless_config: list[dict[str, Any]] = field(default_factory=list)
    wireless_status: list[dict[str, Any]] = field(default_factory=list)
    wireless_devices: list[dict[str, Any]] = field(default_factory=list)
    modems: list[dict[str, Any]] = field(default_factory=list)
    uplink: Uplink | None = None
    wifi_client: WifiClient | None = None
    wifi_first: bool | None = None
    stations: list[WifiStation] = field(default_factory=list)
    access_points: list[AccessPoint] = field(default_factory=list)
    gps: GpsPosition | None = None
    gps_available: bool = False
    # Satellites in use as the router reports them, also without a position.
    gps_satellites: int | None = None
    # The last position that came with a fix, and when; kept by the coordinator.
    gps_last_known: GpsPosition | None = None
    gps_last_fix: datetime | None = None
    multi_ap: list[dict[str, Any]] = field(default_factory=list)
    saved_networks: list[SavedNetwork] = field(default_factory=list)
    router_time: datetime | None = None
    internet: bool | None = None
    portal_waiting: bool = False
    vpn_reachable: bool | None = None
    vpn_latency: float | None = None
    system_usage: SystemUsage | None = None
    dhcp_leases: list[dict[str, Any]] | None = None
    vpn_tunnels: list[VpnTunnel] = field(default_factory=list)
    sim_cards: list[SimCard] = field(default_factory=list)
    failover: list[FailoverInterface] = field(default_factory=list)
    data_limits: list[DataLimit] = field(default_factory=list)
    port_forwards: list[PortForward] = field(default_factory=list)
    traffic_rules: list[TrafficRule] = field(default_factory=list)
    # None means the router has no such page; an empty list is an empty inbox.
    sms: list[SmsMessage] | None = None
    firmware: FirmwareInfo | None = None
    firmware_download: FirmwareDownload | None = None
    vpn_instances: list[VpnInstance] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        *,
        interfaces: list[dict[str, Any]],
        interface_config: list[dict[str, Any]],
        wireless_config: list[dict[str, Any]],
        wireless_status: list[dict[str, Any]],
        wireless_devices: list[dict[str, Any]],
        modems: list[dict[str, Any]],
        gps: dict[str, Any] | None = None,
        multi_ap: list[dict[str, Any]] | None = None,
        router_time: datetime | None = None,
        usage: dict[str, Any] | None = None,
        dhcp_leases: list[dict[str, Any]] | None = None,
        wireguard_config: list[dict[str, Any]] | None = None,
        sim_cards: list[dict[str, Any]] | None = None,
        failover: dict[str, Any] | None = None,
        failover_config: list[dict[str, Any]] | None = None,
        data_limits: list[dict[str, Any]] | None = None,
        port_forwards: list[dict[str, Any]] | None = None,
        traffic_rules: list[dict[str, Any]] | None = None,
        data_plan_bytes: float | None = None,
        sms: list[dict[str, Any]] | None = None,
        firmware_updates: dict[str, Any] | None = None,
        firmware_installed: str | None = None,
        firmware_progress: dict[str, Any] | None = None,
        vpn_config: dict[str, list[dict[str, Any]] | None] | None = None,
        vpn_status: dict[str, Any] | None = None,
    ) -> TeltonikaData:
        """Derive uplink, Wi-Fi client, priority, access points and position."""
        networks = wifi_network_names(wireless_config)
        failover_rows = derive_failover(failover, failover_config, networks)
        offline = {row.name or row.interface_id for row in failover_rows if row.online is False}
        # The Wi-Fi client is matched to the interface the router would like to
        # use, the uplink to the one that works.
        configured_uplink = derive_uplink(interfaces, networks)
        uplink = derive_uplink(interfaces, networks, offline)
        multi_ap = multi_ap or []
        system_usage = derive_system_usage(usage)
        return cls(
            interfaces=interfaces,
            interface_config=interface_config,
            wireless_config=wireless_config,
            wireless_status=wireless_status,
            wireless_devices=wireless_devices,
            modems=modems,
            uplink=uplink,
            wifi_client=derive_wifi_client(
                wireless_status,
                wireless_config,
                wireless_devices,
                configured_uplink.name if configured_uplink else None,
            ),
            wifi_first=derive_wifi_first(interfaces, interface_config, networks),
            stations=derive_stations(wireless_config, interfaces),
            access_points=derive_access_points(
                wireless_config, wireless_status, wireless_devices
            ),
            gps=derive_gps(gps),
            gps_available=bool(gps),
            gps_satellites=to_int(gps.get("satellites")) if isinstance(gps, dict) else None,
            multi_ap=multi_ap,
            saved_networks=derive_saved_networks(
                wireless_config, multi_ap, wireless_devices
            ),
            router_time=system_usage.router_time
            if system_usage and system_usage.router_time
            else router_time,
            system_usage=system_usage,
            dhcp_leases=dhcp_leases,
            vpn_tunnels=derive_vpn_tunnels(interfaces, wireguard_config or []),
            sim_cards=derive_sim_cards(sim_cards),
            failover=failover_rows,
            data_limits=derive_data_limits(data_limits, interface_config, data_plan_bytes),
            port_forwards=derive_port_forwards(port_forwards),
            traffic_rules=derive_traffic_rules(traffic_rules),
            sms=derive_sms(sms),
            firmware=derive_firmware(firmware_installed, firmware_updates),
            firmware_download=derive_firmware_download(firmware_progress),
            vpn_instances=[
                instance
                for kind in VPN_FAMILIES
                for instance in derive_vpn_instances(
                    kind.key,
                    kind.label,
                    kind.enable_key,
                    (vpn_config or {}).get(kind.key),
                    (vpn_status or {}).get(kind.key),
                )
            ],
        )

    @property
    def gps_fix(self) -> bool | None:
        """Return whether the receiver has a fix now, None without GPS."""
        if not self.gps_available:
            return None
        return self.gps is not None and self.gps_satellites != 0

    @property
    def gps_position(self) -> GpsPosition | None:
        """Return the position to show: the live one, else the last known one."""
        if self.gps_fix:
            return self.gps
        return self.gps_last_known or self.gps

    @property
    def wifi_failed(self) -> bool:
        """Return whether the failover calls every Wi-Fi interface offline."""
        rows = [i for i in self.failover if i.kind == UPLINK_WIFI and i.online is not None]
        return bool(rows) and not any(i.online for i in rows)

    @property
    def portal_state(self) -> str:
        """Return the captive portal state."""
        return derive_portal_state(
            waiting=self.portal_waiting,
            wifi_client=self.wifi_client,
            uplink=self.uplink,
            internet=self.internet,
            wifi_failed=self.wifi_failed,
        )

    def modem(self, modem_id: str) -> dict[str, Any] | None:
        """Return one modem by id."""
        for modem in self.modems:
            if str(modem.get("id")) == modem_id:
                return modem
        return None
