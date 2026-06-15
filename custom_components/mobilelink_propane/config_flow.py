from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import MobileLinkApiClient, MobileLinkAuthError
from .const import (
    DOMAIN,
    CONF_COOKIE_HEADER,
    CONF_USERNAME,
    CONF_SELECTED_TANKS,
    OPT_CREATE_LAST_READING_SENSOR,
    OPT_CREATE_CAPACITY_SENSOR,
    OPT_CREATE_BATTERY_SENSOR,
    OPT_CREATE_STATUS_SENSOR,
)

_LOGGER = logging.getLogger(__name__)

class MobileLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2
    reauth_entry = None

    async def async_step_user(self, user_input=None):
        """Initial setup."""
        errors = {}
        if user_input is not None:
            self.username = user_input.get(CONF_USERNAME)
            return await self.async_step_login_guidance()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
            }),
            errors=errors,
            description_placeholders={"login_url": "https://app.mobilelinkgen.com"}
        )

    async def async_step_login_guidance(self, user_input=None):
        """Guide user to login and paste cookie."""
        errors = {}
        if user_input is not None:
            cookie = user_input[CONF_COOKIE_HEADER].strip()
            client = MobileLinkApiClient(self.hass)

            try:
                await client.get_apparatus_list(cookie)
                return self.async_create_entry(
                    title=self.username or "Generac Mobile Link",
                    data={
                        CONF_COOKIE_HEADER: cookie,
                        CONF_USERNAME: self.username,
                    }
                )
            except MobileLinkAuthError:
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="login_guidance",
            data_schema=vol.Schema({
                vol.Required(CONF_COOKIE_HEADER): str,
            }),
            description_placeholders={
                "login_url": "https://app.mobilelinkgen.com",
                "username": getattr(self, 'username', ''),
            },
            errors=errors
        )

    async def async_step_reauth(self, entry_data: dict):
        """Handle reauthentication."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self.username = self.reauth_entry.data.get(CONF_USERNAME)
        return await self.async_step_reauth_guidance()

    async def async_step_reauth_guidance(self, user_input=None):
        """Re-auth flow with guidance."""
        errors = {}
        if user_input is not None:
            cookie = user_input[CONF_COOKIE_HEADER].strip()
            client = MobileLinkApiClient(self.hass)

            try:
                await client.get_apparatus_list(cookie)
                return self.async_update_reload_and_abort(
                    self.reauth_entry,
                    data={**self.reauth_entry.data, CONF_COOKIE_HEADER: cookie}
                )
            except MobileLinkAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_guidance",
            data_schema=vol.Schema({
                vol.Required(CONF_COOKIE_HEADER): str,
            }),
            description_placeholders={
                "login_url": "https://app.mobilelinkgen.com",
                "username": self.username or "",
            },
            errors=errors
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(OPT_CREATE_LAST_READING_SENSOR, default=self.config_entry.options.get(OPT_CREATE_LAST_READING_SENSOR, False)): bool,
                vol.Optional(OPT_CREATE_CAPACITY_SENSOR, default=self.config_entry.options.get(OPT_CREATE_CAPACITY_SENSOR, False)): bool,
                vol.Optional(OPT_CREATE_BATTERY_SENSOR, default=self.config_entry.options.get(OPT_CREATE_BATTERY_SENSOR, False)): bool,
                vol.Optional(OPT_CREATE_STATUS_SENSOR, default=self.config_entry.options.get(OPT_CREATE_STATUS_SENSOR, False)): bool,
            })
        )
