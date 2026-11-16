"""Describe router answers for the debug log and diagnostics without secrets.

Only the structure is shown: key names and value types. Numbers and booleans
are shown unless the key name looks personal, text values only for a short
list of harmless keys. That is enough to see why a feature does not work on
another router model, and it never leaks passwords, PINs, serial numbers,
IMSI/IMEI, SSIDs or addresses.
"""

from __future__ import annotations

import json
import re
from typing import Any

SAFE_STRING_KEYS = frozenset(
    {
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
        "position",
        "primary",
        "modem",
        "operator_state",
        "netstate",
        "simstate",
        "data_conn_state",
        "conntype",
        "wpa_state",
    }
)
SENSITIVE_KEY = re.compile(
    r"key|pass|secret|token|serial|imei|imsi|iccid|mac|addr|ip|host|endpoint|"
    r"ssid|bssid|phone|number|user|psk|cert|pin|puk|latitude|longitude|cellid",
    re.IGNORECASE,
)
MAX_DEPTH = 6
_MAC_KEY = re.compile(r"^(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", re.IGNORECASE)
_IP_KEY = re.compile(
    r"^(?:\d{1,3}(?:\.\d{1,3}){3}(?:/\d+)?|[0-9a-f]*:[0-9a-f:]*:[0-9a-f:./]*)$",
    re.IGNORECASE,
)


def _key_name(key: str) -> str:
    """Replace keys that are addresses, they identify devices of the user."""
    if _MAC_KEY.match(key):
        return "<mac>"
    if _IP_KEY.match(key):
        return "<ip>"
    return key


def describe_shape(value: Any, key: str = "", depth: int = 0) -> Any:
    """Return the structure of a JSON value with few or no values."""
    if depth > MAX_DEPTH:
        return "..."
    if isinstance(value, dict):
        shape: dict[str, Any] = {}
        for k, v in sorted(value.items(), key=lambda item: str(item[0])):
            name = _key_name(str(k))
            # Keys that are addresses (the client list of a radio is keyed by
            # MAC address) collapse into one entry that shows the structure.
            shape.setdefault(name, describe_shape(v, name, depth + 1))
        return shape
    if isinstance(value, list):
        if not value:
            return "[]"
        return {"list": len(value), "first": describe_shape(value[0], key, depth + 1)}
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return "<hidden>" if SENSITIVE_KEY.search(key) else value
    if isinstance(value, str):
        if key in SAFE_STRING_KEYS:
            return value
        return f"str({len(value)})" if value else "str(empty)"
    return type(value).__name__ if value is not None else "null"


def shape_text(value: Any, limit: int = 1500) -> str:
    """Return :func:`describe_shape` as a compact, length limited string."""
    text = json.dumps(
        describe_shape(value), ensure_ascii=False, separators=(",", ":"), default=str
    )
    return text if len(text) <= limit else f"{text[:limit]} ...(cut)"
