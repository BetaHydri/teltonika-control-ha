"""Read-only check of the integration logic against a real router.

Sends only GET requests (plus the login). Reads address and login from the
environment variables TELTONIKA_HOST, TELTONIKA_USER and TELTONIKA_PASSWORD
and prints a summary without serial numbers, addresses or passwords.

Run from the repository root:
    python tools/live_smoke_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.teltonika_control.api import (  # noqa: E402
    TeltonikaClient,
    TeltonikaError,
    parse_host,
)
from custom_components.teltonika_control.models import (  # noqa: E402
    RouterInfo,
    TeltonikaData,
    is_modem_online,
    modem_temperature,
)

EXPECTED_MODEM_KEYS = (
    "id",
    "operator",
    "conntype",
    "simstate",
    "data_conn_state",
    "active_sim",
    "sim_count",
    "rsrp",
    "rsrq",
    "rssi",
    "sinr",
    "band",
    "temperature",
    "rxbytes",
    "txbytes",
)


def mask(value: str | None) -> str:
    return f"***{value[-4:]}" if value else "-"


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
        info = RouterInfo.from_device_status(host, await client.async_device_status())
        interfaces = await client.async_interfaces_status()
        try:
            gps_raw = await client.async_gps_status()
        except TeltonikaError as err:
            gps_raw = {}
            print(f"GPS        : not available ({err})")
        data = TeltonikaData.build(
            interfaces=interfaces,
            interface_config=await client.async_interfaces_config(),
            wireless_config=await client.async_wireless_config(),
            wireless_status=await client.async_wireless_status(),
            wireless_devices=await client.async_wireless_devices_status(),
            modems=await client.async_modems_status(),
            gps=gps_raw,
        )

    print(f"Router     : {info.model} fw {info.firmware} serial {mask(info.serial)}")
    print(
        "Interfaces :",
        [(i.get("id"), i.get("name"), i.get("metric")) for i in interfaces],
    )
    uplink = data.uplink
    print("Uplink     :", uplink and (uplink.kind, uplink.name, uplink.metric))
    print("Wi-Fi first:", data.wifi_first)
    wifi = data.wifi_client
    print("Wi-Fi client:", wifi and (wifi.band, wifi.signal, wifi.bitrate))
    print(
        "Stations   :",
        [(s.config_id, s.network, s.interface_id, s.mode) for s in data.stations],
    )
    print(
        "Radios     :",
        [(d.get("id"), d.get("band"), d.get("frequency")) for d in data.wireless_devices],
    )
    for point in data.access_points:
        print(f"Access pt  : {point.config_id} band={point.band} enabled={point.enabled}")
    if data.wireless_status:
        print("Wireless status keys:", sorted(data.wireless_status[0]))
    if gps_raw:
        print("GPS keys   :", sorted(gps_raw))
        print("GPS parsed :", data.gps or "no fix")

    for modem in data.modems:
        missing = [key for key in EXPECTED_MODEM_KEYS if key not in modem]
        print(
            f"Modem {modem.get('id')}: online={is_modem_online(modem)} "
            f"temp={modem_temperature(modem)} sims={modem.get('sim_count')} "
            f"missing={missing or 'none'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
