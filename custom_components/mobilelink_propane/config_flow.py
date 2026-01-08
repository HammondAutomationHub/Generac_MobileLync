from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import MobileLinkApiClient, MobileLinkAuthError
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SELECTED_TANKS,
    DOMAIN,
    OPT_CREATE_BATTERY_SENSOR,
    OPT_CREATE_CAPACITY_SENSOR,
    OPT_CREATE_LAST_READING_SENSOR,
    OPT_CREATE_STATUS_SENSOR,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPTIONS = {
    OPT_CREATE_LAST_READING_SENSOR: False,
    OPT_CREATE_CAPACITY_SENSOR: False,
    OPT_CREATE_BATTERY_SENSOR: False,
    OPT_CREATE_STATUS_SENSOR: False,
}


async def _login_and_discover(hass: HomeAssistant, email: str, password: str):
    client = MobileLinkApiClient(hass)
    await client.login(email, password)
    tanks = await client.discover_propane_tanks()
    return tanks


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._email: str | None = None
        self._password: str | None = None
        self._tanks: dict[int, str] = {}
        self._last_error_detail: str = ""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]

            try:
                tanks = await _login_and_discover(self.hass, email, password)
            except MobileLinkAuthError as e:
                # Map structured auth errors to user-facing reasons, and log details for troubleshooting.
                self._last_error_detail = f"{e.short()}: {e.detail()}"
                _LOGGER.warning("Mobile Link login failed: %s", self._last_error_detail)

                code = getattr(e, "code", "unknown")
                if code in ("invalid_credentials",):
                    errors["base"] = "invalid_auth"
                elif code in ("password_reset_required",):
                    errors["base"] = "password_reset_required"
                elif code in ("account_locked",):
                    errors["base"] = "account_locked"
                elif code in ("bot_block",):
                    errors["base"] = "bot_block"
                elif code in ("access_denied",):
                    errors["base"] = "access_denied"
                else:
                    errors["base"] = "cannot_connect"
            except Exception as e:
                self._last_error_detail = f"unexpected: {e}"
                _LOGGER.exception("Unexpected error during Mobile Link login/discovery")
                errors["base"] = "cannot_connect"
            else:
                self._email = email
                self._password = password
                self._tanks = {t.apparatus_id: t.name for t in tanks}

                await self.async_set_unique_id(email.lower())
                self._abort_if_unique_id_configured()

                return await self.async_step_select_tanks()

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors, description_placeholders={"error_detail": self._last_error_detail})

    async def async_step_select_tanks(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if not self._tanks:
            return self.async_abort(reason="no_tanks")

        if user_input is not None:
            selected = [int(x) for x in user_input[CONF_SELECTED_TANKS]]
            return self.async_create_entry(
                title=f"Mobile Link ({self._email})",
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_SELECTED_TANKS: selected,
                },
                options=DEFAULT_OPTIONS.copy(),
            )

        tank_options = [
            selector.SelectOptionDict(value=str(k), label=v) for k, v in sorted(self._tanks.items(), key=lambda kv: kv[1].lower())
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_SELECTED_TANKS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=tank_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="select_tanks", data_schema=schema)

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle re-authentication when credentials expire/change."""
        self._email = self.context.get("unique_id")
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                # Try login only
                client = MobileLinkApiClient(self.hass)
                await client.login(self._email, password)
            except MobileLinkAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
                assert entry is not None
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_PASSWORD: password},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        schema = vol.Schema({vol.Required(CONF_PASSWORD): str})
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._tanks: dict[int, str] = {}
        self._last_error_detail: str = ""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_select()

    async def async_step_select(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        email = self.config_entry.data[CONF_EMAIL]
        password = self.config_entry.data[CONF_PASSWORD]
        current_selected = self.config_entry.data.get(CONF_SELECTED_TANKS, [])

        if user_input is not None:
            # update options toggles + selected tanks
            selected = [int(x) for x in user_input[CONF_SELECTED_TANKS]]

            # update entry data for selected tanks
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_SELECTED_TANKS: selected},
                options={
                    OPT_CREATE_LAST_READING_SENSOR: user_input.get(OPT_CREATE_LAST_READING_SENSOR, False),
                    OPT_CREATE_CAPACITY_SENSOR: user_input.get(OPT_CREATE_CAPACITY_SENSOR, False),
                    OPT_CREATE_BATTERY_SENSOR: user_input.get(OPT_CREATE_BATTERY_SENSOR, False),
                    OPT_CREATE_STATUS_SENSOR: user_input.get(OPT_CREATE_STATUS_SENSOR, False),
                },
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Discover tanks fresh so the list is always current
        try:
            tanks = await _login_and_discover(self.hass, email, password)
            self._tanks = {t.apparatus_id: t.name for t in tanks}
        except MobileLinkAuthError:
            errors["base"] = "invalid_auth"
        except Exception:
            errors["base"] = "cannot_connect"

        tank_options = [
            selector.SelectOptionDict(value=str(k), label=v) for k, v in sorted(self._tanks.items(), key=lambda kv: kv[1].lower())
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_SELECTED_TANKS, default=[str(x) for x in current_selected]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=tank_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(OPT_CREATE_LAST_READING_SENSOR, default=self.config_entry.options.get(OPT_CREATE_LAST_READING_SENSOR, False)): bool,
                vol.Optional(OPT_CREATE_CAPACITY_SENSOR, default=self.config_entry.options.get(OPT_CREATE_CAPACITY_SENSOR, False)): bool,
                vol.Optional(OPT_CREATE_BATTERY_SENSOR, default=self.config_entry.options.get(OPT_CREATE_BATTERY_SENSOR, False)): bool,
                vol.Optional(OPT_CREATE_STATUS_SENSOR, default=self.config_entry.options.get(OPT_CREATE_STATUS_SENSOR, False)): bool,
            }
        )
        return self.async_show_form(step_id="select", data_schema=schema, errors=errors)


async def async_get_options_flow(config_entry: config_entries.ConfigEntry):
    return OptionsFlowHandler(config_entry)
