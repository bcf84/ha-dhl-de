"""Config flow for DHL Deutschland."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import DhlApiError, DhlAuthError, DhlClient, decode_jwt_claims, extract_code
from .const import (
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGIN_URL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CONF_LOGIN_CODE = "login_code"
SCHEMA = vol.Schema({vol.Required(CONF_LOGIN_CODE): str})


class DhlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the DHL login."""

    VERSION = 1

    async def _async_login(self, user_input: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any] | None]:
        errors: dict[str, str] = {}
        try:
            code = extract_code(user_input[CONF_LOGIN_CODE])
        except ValueError:
            return {CONF_LOGIN_CODE: "invalid_code"}, None
        client = DhlClient(async_create_clientsession(self.hass))
        try:
            tokens = await client.async_login_with_code(code)
        except DhlAuthError:
            errors["base"] = "invalid_auth"
        except DhlApiError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during DHL login")
            errors["base"] = "unknown"
        else:
            return errors, tokens
        return errors, None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show login link and ask for the dhllogin:// URL."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, tokens = await self._async_login(user_input)
            if tokens:
                claims = decode_jwt_claims(tokens.get("id_token"))
                unique = claims.get("sub") or claims.get("email") or claims.get("post_number")
                if unique:
                    await self.async_set_unique_id(str(unique))
                    self._abort_if_unique_id_configured()
                title = claims.get("display_name") or claims.get("email") or "DHL"
                return self.async_create_entry(
                    title=f"DHL ({title})",
                    data={CONF_REFRESH_TOKEN: tokens["refresh_token"]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
            description_placeholders={"login_url": LOGIN_URL},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start reauth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for a new code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, tokens = await self._async_login(user_input)
            if tokens:
                entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_REFRESH_TOKEN: tokens["refresh_token"]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=SCHEMA,
            errors=errors,
            description_placeholders={"login_url": LOGIN_URL},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options."""
        return DhlOptionsFlow()


class DhlOptionsFlow(OptionsFlow):
    """Polling interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=1440)
                    )
                }
            ),
        )
