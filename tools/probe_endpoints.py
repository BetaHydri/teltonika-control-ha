"""Read-only probe of RutOS REST endpoints that the integration does not use yet.

Standalone: needs only Python 3.10+ and ``pip install aiohttp``. It does not
need Home Assistant or this repository's code.

Sends only GET requests (plus the login). For every endpoint it prints whether
it exists and the structure of the answer: key names and value types. Numbers
and booleans are shown, text values only for a short list of harmless keys, so
keys, addresses, names and serial numbers never appear in the output. You can
paste the result into an issue or a chat.

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
    # System
    "/system/device/status",
    "/system/device/usage/status",
    "/system/status",
    "/system/info",
    "/system/uptime",
    "/firmware/device/status",
    "/firmware/status",
    "/firmware/fota/status",
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
    # Others
    "/modems/status",
    "/modems/config",
    "/modems/sims/config",
    "/logs/system",
    "/logs/kernel",
    "/logs",
    "/messages/status",
    "/sms_utils/messages/status",
    "/data_limit/config",
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
}
SENSITIVE = re.compile(
    r"key|pass|secret|token|serial|imei|imsi|iccid|mac|addr|ip|host|endpoint|"
    r"ssid|bssid|phone|number|user|name|psk|cert|pin|puk",
    re.IGNORECASE,
)
MAX_LINE = 1800


def describe(value: Any, key: str = "") -> Any:
    """Return a harmless picture of a JSON value: names and types, few values."""
    if isinstance(value, dict):
        return {k: describe(v, k) for k, v in sorted(value.items())}
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
        return data


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
                ):
                    await probe.get(path)

        interfaces = results.get("/interfaces/status")
        if isinstance(interfaces, list):
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
