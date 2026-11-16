"""Async client for the Teltonika RutOS REST API (RUTC and RUTX routers)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import aiohttp

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)
ACTION_TIMEOUT = aiohttp.ClientTimeout(total=45)
TOKEN_SAFETY_MARGIN = 20
DEFAULT_TOKEN_LIFETIME = 300
ERROR_CODE_UNAUTHORIZED = 120


class TeltonikaError(Exception):
    """Base error of the Teltonika client."""


class TeltonikaConnectionError(TeltonikaError):
    """The router cannot be reached."""


class TeltonikaAuthError(TeltonikaError):
    """The router rejected the credentials or the token."""


class TeltonikaApiError(TeltonikaError):
    """The router answered with an error."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def parse_host(value: str) -> tuple[str, bool]:
    """Split user input into host[:port] and whether HTTPS is used."""
    host = value.strip().rstrip("/")
    use_ssl = True
    lowered = host.lower()
    if lowered.startswith("http://"):
        host, use_ssl = host[7:], False
    elif lowered.startswith("https://"):
        host = host[8:]
    return host.split("/", 1)[0], use_ssl


async def _read_body(response: aiohttp.ClientResponse) -> dict[str, Any]:
    try:
        body = await response.json(content_type=None)
    except (aiohttp.ContentTypeError, ValueError):
        return {}
    return body if isinstance(body, dict) else {}


def _first_error(body: dict[str, Any]) -> tuple[str | None, int | None]:
    errors = body.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        code = errors[0].get("code")
        return errors[0].get("error"), code if isinstance(code, int) else None
    return None, None


def _http_date(value: str | None) -> datetime | None:
    """Parse the Date header of an answer, None if missing or invalid."""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class TeltonikaClient:
    """Token based client for one router."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
        *,
        use_ssl: bool = True,
    ) -> None:
        scheme = "https" if use_ssl else "http"
        self._session = session
        self._host = host
        self._base_url = f"{scheme}://{host}/api"
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._login_lock = asyncio.Lock()
        self._server_time: datetime | None = None

    @property
    def host(self) -> str:
        """Return host[:port] of the router."""
        return self._host

    @property
    def server_time(self) -> datetime | None:
        """Return the router clock from the Date header of the last answer."""
        return self._server_time

    async def async_login(self) -> None:
        """Log in and remember the session token."""
        try:
            async with self._session.post(
                f"{self._base_url}/login",
                json={"username": self._username, "password": self._password},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                status = response.status
                body = await _read_body(response)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TeltonikaConnectionError(
                f"Cannot reach {self._host}: {err}"
            ) from err

        if status >= 500:
            raise TeltonikaApiError(f"Router error {status}", status=status)
        if status >= 400 or not body.get("success"):
            message, _ = _first_error(body)
            raise TeltonikaAuthError(message or "Login failed")

        data = body.get("data") or {}
        token = data.get("token")
        if not isinstance(token, str) or not token:
            raise TeltonikaApiError("Login response contains no token")
        try:
            lifetime = float(data.get("expires", DEFAULT_TOKEN_LIFETIME))
        except (TypeError, ValueError):
            lifetime = DEFAULT_TOKEN_LIFETIME
        self._token = token
        self._token_expires_at = time.monotonic() + lifetime - TOKEN_SAFETY_MARGIN

    async def _async_ensure_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        async with self._login_lock:
            if not self._token or time.monotonic() >= self._token_expires_at:
                await self.async_login()
        assert self._token is not None
        return self._token

    async def async_request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        timeout: aiohttp.ClientTimeout = REQUEST_TIMEOUT,  # noqa: ASYNC109
        _retry: bool = True,
    ) -> Any:
        """Call the API and return the ``data`` member of the answer."""
        token = await self._async_ensure_token()
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                json=json,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            ) as response:
                status = response.status
                body = await _read_body(response)
                self._server_time = _http_date(response.headers.get("Date")) or (
                    self._server_time
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TeltonikaConnectionError(
                f"Cannot reach {self._host}: {err}"
            ) from err

        message, code = _first_error(body)
        if status == 401 or code == ERROR_CODE_UNAUTHORIZED:
            self._token = None
            if _retry:
                return await self.async_request(
                    method,
                    path,
                    json=json,
                    params=params,
                    timeout=timeout,
                    _retry=False,
                )
            raise TeltonikaAuthError(message or "Token rejected")
        if status >= 400 or body.get("success") is False:
            raise TeltonikaApiError(
                message or f"{method} {path} failed with HTTP {status}",
                status=status,
                code=code,
            )
        return body.get("data")

    async def _async_list(self, path: str) -> list[dict[str, Any]]:
        data = await self.async_request("GET", path)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    async def async_device_status(self) -> dict[str, Any]:
        """Return model, serial number and firmware of the router."""
        data = await self.async_request("GET", "/system/device/status")
        return data if isinstance(data, dict) else {}

    async def async_interfaces_status(self) -> list[dict[str, Any]]:
        """Return all network interfaces with routes and metrics."""
        return await self._async_list("/interfaces/status")

    async def async_interfaces_config(self) -> list[dict[str, Any]]:
        """Return the configuration of all network interfaces."""
        return await self._async_list("/interfaces/config")

    async def async_wireless_config(self) -> list[dict[str, Any]]:
        """Return access points, Wi-Fi clients and Multi AP entries."""
        return await self._async_list("/wireless/interfaces/config")

    async def async_wireless_status(self) -> list[dict[str, Any]]:
        """Return the live state of all Wi-Fi interfaces."""
        return await self._async_list("/wireless/interfaces/status")

    async def async_wireless_devices_status(self) -> list[dict[str, Any]]:
        """Return the Wi-Fi radios with their band."""
        return await self._async_list("/wireless/devices/status")

    async def async_modems_status(self) -> list[dict[str, Any]]:
        """Return the live state of all modems."""
        return await self._async_list("/modems/status")

    async def async_gps_status(self) -> dict[str, Any]:
        """Return the GPS position; routers without GPS answer with an error."""
        data = await self.async_request("GET", "/gps/position/status")
        return data if isinstance(data, dict) else {}

    async def async_restart_modem_connection(self, modem_id: str) -> None:
        """Re-establish the mobile data connection."""
        await self.async_request(
            "POST",
            f"/modems/{quote(modem_id, safe='')}/actions/restart_connection",
            timeout=ACTION_TIMEOUT,
        )

    async def async_switch_sim(self, modem_id: str) -> None:
        """Switch the modem to its next SIM slot."""
        await self.async_request(
            "POST",
            f"/modems/{quote(modem_id, safe='')}/actions/switch_sim",
            timeout=ACTION_TIMEOUT,
        )

    async def async_reboot(self) -> None:
        """Reboot the router."""
        await self.async_request(
            "POST", "/system/actions/reboot", timeout=ACTION_TIMEOUT
        )

    async def async_set_interface_metric(self, interface_id: str, metric: str) -> None:
        """Set the routing metric of a network interface."""
        await self.async_request(
            "PUT",
            f"/interfaces/config/{quote(interface_id, safe='')}",
            json={"data": {"metric": str(metric)}},
        )

    async def async_set_wireless_enabled(
        self, wireless_id: str, enabled: bool
    ) -> None:
        """Enable or disable a Wi-Fi interface such as an access point."""
        await self.async_request(
            "PUT",
            f"/wireless/interfaces/config/{quote(wireless_id, safe='')}",
            json={"data": {"enabled": "1" if enabled else "0"}},
        )

    async def async_reconnect_wifi(self, station_id: str) -> None:
        """Make a Wi-Fi client reconnect to its network."""
        await self.async_request(
            "POST",
            "/wireless/actions/reconnect",
            json={"data": {"sta_id": str(station_id)}},
            timeout=ACTION_TIMEOUT,
        )

    async def async_scan_wifi(self, radio: str) -> list[dict[str, Any]]:
        """Scan for networks with one radio."""
        data = await self.async_request(
            "POST",
            "/wireless/actions/scan",
            json={"data": {"device": radio}},
            timeout=ACTION_TIMEOUT,
        )
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    async def async_join_wifi(
        self,
        *,
        radio: str,
        ssid: str,
        bssid: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        """Save a network as Wi-Fi client; the router creates the interface."""
        payload: dict[str, Any] = {"device": radio, "ssid": ssid}
        if bssid:
            payload["bssid"] = bssid
        if password:
            payload["password"] = password
        data = await self.async_request(
            "POST",
            "/wireless/actions/join",
            json={"data": payload},
            params={"use_cache": "true"},
            timeout=ACTION_TIMEOUT,
        )
        return data if isinstance(data, dict) else {}

    async def async_delete_wireless(self, wireless_id: str) -> None:
        """Remove a saved Wi-Fi interface."""
        await self.async_request(
            "DELETE",
            f"/wireless/interfaces/config/{quote(wireless_id, safe='')}",
        )

    async def async_delete_interface(self, interface_id: str) -> None:
        """Remove a network interface."""
        await self.async_request(
            "DELETE", f"/interfaces/config/{quote(interface_id, safe='')}"
        )

    async def async_multi_ap_config(self) -> list[dict[str, Any]]:
        """Return the saved networks of a Multi AP radio."""
        return await self._async_list("/wireless/multi_ap/config")

    async def async_add_multi_ap(
        self, *, ssid: str, password: str | None, priority: int
    ) -> None:
        """Add a network to the Multi AP list."""
        payload: dict[str, Any] = {
            "ssid": ssid,
            "enabled": "1",
            "priority": str(priority),
        }
        if password:
            payload["key"] = password
        await self.async_request(
            "POST", "/wireless/multi_ap/config", json={"data": payload}
        )

    async def async_update_multi_ap_key(self, entry_id: str, password: str) -> None:
        """Change the password of a Multi AP list entry."""
        await self.async_request(
            "PUT",
            f"/wireless/multi_ap/config/{quote(entry_id, safe='')}",
            json={"data": {"key": password}},
        )

    async def async_delete_multi_ap(self, entry_id: str) -> None:
        """Remove an entry from the Multi AP list."""
        await self.async_request(
            "DELETE", f"/wireless/multi_ap/config/{quote(entry_id, safe='')}"
        )
