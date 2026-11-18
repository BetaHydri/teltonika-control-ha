"""Read-only probe of RutOS REST endpoints that the integration does not use yet.

Standalone: needs only Python 3.10+ and ``pip install aiohttp``. It does not
need Home Assistant or this repository's code.

Sends only GET requests (plus the login). For every endpoint it prints whether
it exists and the structure of the answer: key names and value types. Numbers
and booleans are shown, text values only for a short list of harmless keys, so
keys, addresses, names and serial numbers never appear in the output. You can
paste the result into an issue or a chat. At the end it prints a table of the
network interfaces (names, types, failover use); interface names are not
personal data.

Set the router address and login in environment variables, then run it:

    PowerShell:
        $env:TELTONIKA_HOST = "192.168.1.1"
        $env:TELTONIKA_USER = "your-user"
        $env:TELTONIKA_PASSWORD = "your-password"
        python tools/probe_endpoints.py

    Linux or WSL:
        TELTONIKA_HOST=192.168.1.1 TELTONIKA_USER=your-user \\
        TELTONIKA_PASSWORD=your-password python3 tools/probe_endpoints.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=15)

CANDIDATES = (
    # VPN
    "/wireguard/config",
    "/wireguard/status",
    "/wireguard/peers/config",
    "/wireguard/peers/status",
    "/openvpn/config",
    "/openvpn/status",
    "/ipsec/config",
    "/ipsec/status",
    "/zerotier/config",
    "/tailscale/config",
    "/tailscale/status",
    "/sstp/config",
    "/sstp/status",
    # System
    "/system/device/status",
    "/system/device/usage/status",
    "/system/status",
    "/system/info",
    "/system/uptime",
    "/firmware/device/status",
    "/firmware/device/updates/status",
    "/firmware/device/progress/status",
    "/firmware/modem/updates/status",
    "/firmware/status",
    "/firmware/fota/status",
    "/speedtest/status",
    "/vrrp/status",
    "/ddns/status",
    "/hotspot/status",
    # Network
    "/interfaces/status",
    "/dhcp/leases/ipv4/status",
    "/dhcp/leases/status",
    "/network/devices/status",
    "/network/wan/status",
    "/failover/status",
    "/failover/rules/config",
    "/failover/interfaces/config",
    "/multiwan/status",
    "/firewall/port_forwards/config",
    "/firewall/rules/config",
    "/firewall/traffic_rules/config",
    "/firewall/zones/config",
    "/firewall/nat_rules/config",
    # Others
    "/modems/status",
    "/modems/config",
    "/modems/sims/config",
    # Where could the SIM settings (deny roaming) be? The probe marks every
    # answer that contains a key with "roaming" in its name.
    "/sims/config",
    "/sim/config",
    "/simcards/config",
    "/sim_cards/config",
    "/simcard/config",
    "/sims",
    "/sim",
    "/simcards",
    "/simcard",
    "/modems/sim/config",
    "/modems/sims",
    "/modems/simcards/config",
    "/modems/simcard/config",
    "/modems/sim_cards/config",
    "/modems/sim_config",
    "/modems/apns/config",
    "/modems/apns",
    "/modems/general/config",
    "/modems/roaming/config",
    "/modems/config/sim",
    "/modem/config",
    "/modem/sims/config",
    "/mobile/config",
    "/mobile/sims/config",
    "/mobile/general/config",
    "/mobile/sim/config",
    "/network/mobile/config",
    "/network/mobile/sims/config",
    "/logs/system",
    "/logs/kernel",
    "/logs",
    "/messages/status",
    "/sms_utils/messages/status",
    "/data_limit/config",
    "/data_limit/status",
    "/data_usage/month/status",
    "/data_usage/day/status",
    "/io/status",
    "/ntp/config",
)

SAFE_STRING_KEYS = {
    "proto",
    "protocol",
    "status",
    "state",
    "type",
    "mode",
    "enabled",
    "up",
    "available",
    "role",
    "ifname",
    "deny_roaming",
    "roaming",
    "data_roaming",
    "allow_roaming",
    "primary",
    "sim",
    "sim_id",
    "default_sim",
    # Firmware versions, speed test results and message dates: they say which
    # format and unit the router uses. No names, numbers or texts of messages.
    "version",
    "stable_version",
    "kernel_version",
    "build_date",
    "date",
    "stable_date",
    "size",
    "stable_size",
    "percents",
    "process",
    "update_exists",
    "avgDownloadSpeed",
    "avgUploadSpeed",
    "downloaded",
    "uploaded",
    "startTime",
}
SENSITIVE = re.compile(
    r"key|pass|secret|token|serial|imei|imsi|iccid|mac|addr|ip|host|endpoint|"
    r"ssid|bssid|phone|number|user|name|psk|cert|pin|puk",
    re.IGNORECASE,
)
MAX_LINE = 1800
ADDRESS_KEY = re.compile(
    r"^(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}$|^\d{1,3}(?:\.\d{1,3}){3}(?:/\d+)?$",
    re.IGNORECASE,
)


def describe(value: Any, key: str = "") -> Any:
    """Return a harmless picture of a JSON value: names and types, few values."""
    if isinstance(value, dict):
        shape: dict[str, Any] = {}
        for k, v in sorted(value.items()):
            name = "<address>" if ADDRESS_KEY.match(str(k)) else k
            shape.setdefault(name, describe(v, name))
        return shape
    if isinstance(value, list):
        if not value:
            return "[]"
        return {"list": len(value), "first": describe(value[0], key)}
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return "<hidden>" if SENSITIVE.search(key) else value
    if isinstance(value, str):
        if key in SAFE_STRING_KEYS:
            return value
        return f"str({len(value)})" if value else "str(empty)"
    return type(value).__name__


def find_keys(value: Any, needle: str, path: str = "") -> list[tuple[str, Any]]:
    """Find keys that contain ``needle`` anywhere in a JSON value."""
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{path}.{key}" if path else str(key)
            if needle in str(key).lower():
                shown = item if isinstance(item, (bool, int, float, str)) else type(item).__name__
                found.append((here, shown))
            found.extend(find_keys(item, needle, here))
    elif isinstance(value, list):
        for index, item in enumerate(value[:20]):
            found.extend(find_keys(item, needle, f"{path}[{index}]"))
    return found


def usage_rows(data: Any) -> list[str]:
    """Show the entries of a data usage answer: time, received and sent."""
    rows = data.get("usage") if isinstance(data, dict) else data
    lines: list[str] = []
    for entry in rows[:40] if isinstance(rows, list) else []:
        if (
            isinstance(entry, list)
            and len(entry) == 3
            and all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in entry)
        ):
            stamp = datetime.fromtimestamp(entry[0], UTC).strftime("%Y-%m-%d %H:%M")
            lines.append(f"     {stamp} UTC  rx={entry[1]}  tx={entry[2]}")
    return lines


class Probe:
    def __init__(self, session: aiohttp.ClientSession, base: str) -> None:
        self._session = session
        self._base = base
        self._token = ""

    async def login(self, user: str, password: str) -> None:
        async with self._session.post(
            f"{self._base}/login",
            json={"username": user, "password": password},
            timeout=TIMEOUT,
        ) as response:
            body = await response.json(content_type=None)
        token = (body or {}).get("data", {}).get("token")
        if not token:
            raise SystemExit("Login failed: check address, user and password.")
        self._token = token

    async def get(self, path: str) -> Any | None:
        """GET a path, print what came back, return the data member."""
        try:
            async with self._session.get(
                f"{self._base}{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=TIMEOUT,
            ) as response:
                status = response.status
                try:
                    body = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    body = None
        except (aiohttp.ClientError, TimeoutError) as err:
            print(f"--   GET {path}  {type(err).__name__}")
            return None
        if status >= 400 or not isinstance(body, dict) or body.get("success") is False:
            print(f"--   GET {path}  HTTP {status}")
            return None
        data = body.get("data")
        text = json.dumps(describe(data), ensure_ascii=False, separators=(",", ":"))
        if len(text) > MAX_LINE:
            text = text[:MAX_LINE] + " ...(cut)"
        print(f"OK   GET {path}\n     {text}")
        if path.startswith("/data_usage/"):
            for line in usage_rows(data):
                print(line)
        for key_path, shown in find_keys(data, "roaming"):
            print(f"     >>> ROAMING {key_path} = {shown!r}")
        return data


def print_interface_table(
    interfaces: Any, failover_config: Any, wireless_config: Any = None
) -> None:
    """Print what each network interface is: its name, type and failover use.

    Interface names and types are not personal data. Wi-Fi network names and
    addresses are not printed.
    """
    print("\nInterfaces (/interfaces/status):")
    if isinstance(interfaces, list):
        for item in interfaces:
            if not isinstance(item, dict):
                continue
            route = any(
                isinstance(r, dict) and r.get("target") == "0.0.0.0" and r.get("mask") == 0
                for r in item.get("route") or []
            )
            print(
                "    id={id} name={name} ifname={ifname} proto={proto} type={type} "
                "up={up} metric={metric} mwan_enabled={mwan} default_route={route}".format(
                    id=item.get("id"),
                    name=item.get("name"),
                    ifname=item.get("ifname"),
                    proto=item.get("proto"),
                    type=item.get("type"),
                    up=item.get("up"),
                    metric=item.get("metric"),
                    mwan=item.get("mwan_enabled"),
                    route=route,
                )
            )
    print("\nFailover interfaces (/failover/interfaces/config):")
    if isinstance(failover_config, list):
        for item in failover_config:
            if isinstance(item, dict):
                print(
                    "    id={id} name={name} enabled={enabled} network_type={nt} "
                    "family={family} track_method={method}".format(
                        id=item.get("id"),
                        name=item.get("name"),
                        enabled=item.get("enabled"),
                        nt=item.get("network_type"),
                        family=item.get("family"),
                        method=item.get("track_method"),
                    )
                )
    print("\nWi-Fi interfaces (/wireless/interfaces/config), no names:")
    if isinstance(wireless_config, list):
        for item in wireless_config:
            if isinstance(item, dict):
                print(
                    "    id={id} mode={mode} device={device} network={network} "
                    "enabled={enabled}".format(
                        id=item.get("id"),
                        mode=item.get("mode"),
                        device=item.get("device"),
                        network=item.get("network"),
                        enabled=item.get("enabled"),
                    )
                )


def _joined(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return "-" if value in (None, "") else str(value)


def print_firewall_table(zones: Any, rules: Any, forwards: Any) -> None:
    """Print the firewall zones (with their networks), traffic rules and forwards.

    Zone names, rule names and port numbers are router settings, not personal
    data. IP addresses and MAC addresses are not printed.
    """
    print("\nFirewall zones (/firewall/zones/config):")
    if isinstance(zones, list):
        for item in zones:
            if isinstance(item, dict):
                print(
                    "    name={name} networks={net} input={i} output={o} forward={f} "
                    "masq={masq} extra_src={src}".format(
                        name=item.get("name"),
                        net=_joined(item.get("network")),
                        i=item.get("input"),
                        o=item.get("output"),
                        f=item.get("forward"),
                        masq=item.get("masq"),
                        src=_joined(item.get("extra_src")),
                    )
                )
    print("\nTraffic rules (/firewall/traffic_rules/config):")
    if isinstance(rules, list):
        for item in rules:
            if isinstance(item, dict):
                print(
                    "    id={id} name={name} enabled={en} src={src} dest={dest} "
                    "proto={proto} dest_port={port} target={target} family={fam}".format(
                        id=item.get("id"),
                        name=item.get("name"),
                        en=item.get("enabled"),
                        src=item.get("src"),
                        dest=item.get("dest"),
                        proto=_joined(item.get("proto")),
                        port=item.get("dest_port"),
                        target=item.get("target"),
                        fam=item.get("family"),
                    )
                )
    print("\nPort forwards (/firewall/port_forwards/config):")
    if isinstance(forwards, list):
        for item in forwards:
            if isinstance(item, dict):
                print(
                    "    id={id} name={name} enabled={en} src={src} dest={dest} "
                    "src_dport={sp} dest_port={dp} reflection={refl}".format(
                        id=item.get("id"),
                        name=item.get("name"),
                        en=item.get("enabled"),
                        src=item.get("src"),
                        dest=item.get("dest"),
                        sp=item.get("src_dport"),
                        dp=item.get("dest_port"),
                        refl=item.get("reflection"),
                    )
                )


async def main() -> int:
    try:
        host = os.environ["TELTONIKA_HOST"].strip().rstrip("/")
        user = os.environ["TELTONIKA_USER"]
        password = os.environ["TELTONIKA_PASSWORD"]
    except KeyError as err:
        print(f"Set the environment variable {err.args[0]} first.")
        return 2

    scheme = "http" if host.startswith("http://") else "https"
    host = re.sub(r"^https?://", "", host)
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        probe = Probe(session, f"{scheme}://{host}/api")
        await probe.login(user, password)
        results = {path: await probe.get(path) for path in CANDIDATES}
        wireless = await probe.get("/wireless/interfaces/config")
        print_interface_table(
            results.get("/interfaces/status"),
            results.get("/failover/interfaces/config"),
            wireless,
        )
        print_firewall_table(
            results.get("/firewall/zones/config"),
            results.get("/firewall/traffic_rules/config"),
            results.get("/firewall/port_forwards/config"),
        )

        # Peers and details of every WireGuard instance.
        instances = results.get("/wireguard/config")
        if isinstance(instances, list):
            for instance in instances:
                instance_id = instance.get("id") if isinstance(instance, dict) else None
                if not instance_id:
                    continue
                safe_id = quote(str(instance_id), safe="")
                await probe.get(f"/wireguard/config/{safe_id}")
                await probe.get(f"/wireguard/config/{safe_id}/peers")
                await probe.get(f"/wireguard/status/{safe_id}")

        # Modem configuration (roaming, SIM settings) per modem.
        modems = results.get("/modems/status")
        if isinstance(modems, list):
            for modem in modems:
                modem_id = modem.get("id") if isinstance(modem, dict) else None
                if not modem_id:
                    continue
                safe_id = quote(str(modem_id), safe="")
                for path in (
                    f"/modems/{safe_id}",
                    f"/modems/config/{safe_id}",
                    f"/modems/{safe_id}/config",
                    f"/modems/{safe_id}/sims",
                    f"/modems/{safe_id}/sims/config",
                    f"/modems/{safe_id}/sims/1",
                    f"/modems/{safe_id}/sim_config",
                    f"/modems/{safe_id}/sim_cards",
                    f"/modems/config/{safe_id}/sim",
                    f"/modems/config/{safe_id}/sims",
                    f"/modems/{safe_id}/sim/config",
                    f"/modems/{safe_id}/sim/1",
                    f"/modems/{safe_id}/sim/1/config",
                    f"/modems/{safe_id}/sims/1/config",
                    f"/modems/{safe_id}/sims/2/config",
                    f"/modems/{safe_id}/simcards",
                    f"/modems/{safe_id}/simcard/config",
                    f"/modems/{safe_id}/roaming",
                    f"/modems/{safe_id}/apns/config",
                    f"/data_usage/month/modem/{safe_id}/status",
                    f"/data_usage/month/modem/{safe_id}/sim/1/status",
                    f"/data_usage/month/modem/{safe_id}/sim/2/status",
                ):
                    await probe.get(path)

        interfaces = results.get("/interfaces/status")
        if isinstance(interfaces, list):
            for item in interfaces:
                name = item.get("id") if isinstance(item, dict) else None
                if name and str(name).startswith("mob"):
                    await probe.get(
                        f"/data_usage/month/interface/{quote(str(name), safe='')}/status"
                    )
            vpn = [
                describe(item)
                for item in interfaces
                if isinstance(item, dict)
                and re.search(
                    r"wg|vpn|tun|ipsec|zt|tailscale", str(item.get("id", "")), re.I
                )
            ]
            print(f"\nVPN-like entries in /interfaces/status: {len(vpn)}")
            for item in vpn:
                print(
                    "    ",
                    json.dumps(item, ensure_ascii=False, separators=(",", ":"))[
                        :MAX_LINE
                    ],
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
