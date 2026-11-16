"""Read-only probe of RutOS REST endpoints that the integration does not use yet.

Sends only GET requests (plus the login). For every endpoint it prints whether
it exists and the structure of the answer: key names and value types. Numbers
and booleans are shown, text values only for a short list of harmless keys, so
keys, addresses, names and serial numbers never appear in the output. You can
paste the result into an issue or a chat.

Reads address and login from TELTONIKA_HOST, TELTONIKA_USER and
TELTONIKA_PASSWORD. Run from the repository root:
    python tools/probe_endpoints.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.teltonika_control.api import (  # noqa: E402
    TeltonikaApiError,
    TeltonikaClient,
    TeltonikaError,
    parse_host,
)

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
    "/system/actions",
    "/firmware/device/status",
    "/firmware/status",
    "/firmware/actions/fota_info",
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
}
SENSITIVE = re.compile(
    r"key|pass|secret|token|serial|imei|imsi|iccid|mac|addr|ip|host|endpoint|"
    r"ssid|bssid|phone|number|user|name|psk|cert",
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


def show(path: str, picture: Any) -> None:
    text = json.dumps(picture, ensure_ascii=False, separators=(",", ":"))
    if len(text) > MAX_LINE:
        text = text[:MAX_LINE] + " ...(cut)"
    print(f"OK   GET {path}\n     {text}")


async def probe(client: TeltonikaClient, path: str) -> Any | None:
    try:
        data = await client.async_request("GET", path)
    except TeltonikaApiError as err:
        print(f"--   GET {path}  HTTP {err.status or '?'}: {str(err)[:80]}")
        return None
    except TeltonikaError as err:
        print(f"--   GET {path}  {str(err)[:80]}")
        return None
    show(path, describe(data))
    return data


async def main() -> int:
    try:
        host_input = os.environ["TELTONIKA_HOST"]
        user = os.environ["TELTONIKA_USER"]
        password = os.environ["TELTONIKA_PASSWORD"]
    except KeyError as err:
        print(f"Set the environment variable {err.args[0]} first.")
        return 2

    host, use_ssl = parse_host(host_input)
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        client = TeltonikaClient(session, host, user, password, use_ssl=use_ssl)
        await client.async_login()
        results: dict[str, Any] = {}
        for path in CANDIDATES:
            results[path] = await probe(client, path)

        # Peers and per-instance details of every WireGuard instance.
        instances = results.get("/wireguard/config")
        if isinstance(instances, list):
            for instance in instances:
                instance_id = instance.get("id") if isinstance(instance, dict) else None
                if not instance_id:
                    continue
                safe_id = quote(str(instance_id), safe="")
                await probe(client, f"/wireguard/config/{safe_id}")
                await probe(client, f"/wireguard/config/{safe_id}/peers")
                await probe(client, f"/wireguard/status/{safe_id}")
                await probe(client, f"/wireguard/peers/config?instance={safe_id}")

        interfaces = results.get("/interfaces/status")
        if isinstance(interfaces, list):
            vpn = [
                describe(item)
                for item in interfaces
                if isinstance(item, dict)
                and re.search(r"wg|vpn|tun|ipsec|zt|tailscale", str(item.get("id", "")), re.I)
            ]
            print(f"\nVPN-like entries in /interfaces/status: {len(vpn)}")
            for item in vpn:
                print("    ", json.dumps(item, ensure_ascii=False, separators=(",", ":"))[:MAX_LINE])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
