"""Config flow for Teltonika Control."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    TeltonikaAuthError,
    TeltonikaClient,
    TeltonikaConnectionError,
    TeltonikaError,
    parse_host,
)
from .const import (
    CONF_PROBE_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_PROBE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .models import RouterInfo

_LOGGER = logging.getLogger(__name__)


def build_client(hass: HomeAssistant, data: Mapping[str, Any]) -> TeltonikaClient:
    """Create a client from config entry data."""
    host, use_ssl = parse_host(data[CONF_HOST])
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, False))
    return TeltonikaClient(
        session,
        host,
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        use_ssl=use_ssl,
    )


async def async_validate(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> RouterInfo:
    """Log in and read the router identity."""
    client = build_client(hass, data)
    await client.async_login()
    status = await client.async_device_status()
    return RouterInfo.from_device_status(client.host, status)


class TeltonikaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup of one router."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> TeltonikaOptionsFlow:
        """Return the options flow."""
        return TeltonikaOptionsFlow()

    async def _async_try(
        self, data: Mapping[str, Any]
    ) -> tuple[RouterInfo | None, dict[str, str]]:
        try:
            return await async_validate(self.hass, data), {}
        except TeltonikaAuthError:
            return None, {"base": "invalid_auth"}
        except TeltonikaConnectionError:
            return None, {"base": "cannot_connect"}
        except TeltonikaError:
            _LOGGER.exception("Unexpected router answer")
            return None, {"base": "unknown"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host and credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._async_try(user_input)
            if info is not None:
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(title=info.name, data=user_input)

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "192.168.1.1")): str,
                    vol.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(
                        CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, False)
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication after the router rejected the login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            info, errors = await self._async_try(data)
            if info is not None:
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host, user or password of an existing router."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._async_try(user_input)
            if info is not None:
                await self.async_set_unique_id(info.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=user_input)

        current = user_input or entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current[CONF_HOST]): str,
                    vol.Required(CONF_USERNAME, default=current[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(
                        CONF_VERIFY_SSL, default=current.get(CONF_VERIFY_SSL, False)
                    ): bool,
                }
            ),
            errors=errors,
        )


class TeltonikaOptionsFlow(OptionsFlow):
    """Polling interval and internet probe."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # An emptied field is missing from user_input: store "" to disable the probe.
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_PROBE_URL: user_input.get(CONF_PROBE_URL, "").strip(),
                }
            )

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Optional(
                        CONF_PROBE_URL,
                        description={
                            "suggested_value": options.get(
                                CONF_PROBE_URL, DEFAULT_PROBE_URL
                            )
                        },
                    ): str,
                }
            ),
        )
