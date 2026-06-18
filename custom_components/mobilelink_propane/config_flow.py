from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import MobileLinkApiClient, MobileLinkAuthError, MobileLinkApiError
from .const import (
    CONF_COOKIE_HEADER,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SELECTED_TANKS,
    CONF_USERNAME,
    DEFAULT_OPTIONS,
    DOMAIN,
    LOGIN_URL,
    OPT_CREATE_BATTERY_SENSOR,
    OPT_CREATE_CAPACITY_SENSOR,
    OPT_CREATE_LAST_READING_SENSOR,
    OPT_CREATE_STATUS_SENSOR,
)
from .util import normalize_cookie_header

_LOGGER = logging.getLogger(__name__)


async def _discover_tanks(hass: HomeAssistant, cookie_header: str) -> dict[int, str]:
    client = MobileLinkApiClient(hass)
    apparatus = await client.get_apparatus_list(cookie_header)
    tanks = client.parse_propane_tanks(apparatus)
    return {tank.apparatus_id: tank.name for tank in tanks}


def _tank_selector(tanks: dict[int, str]) -> selector.SelectSelector:
    options = [
        selector.SelectOptionDict(value=str(apparatus_id), label=name)
        for apparatus_id, name in sorted(tanks.items(), key=lambda item: item[1].lower())
    ]
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
            sort=True,
            custom_value=False,
        )
    )


class MobileLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    def __init__(self) -> None:
        self._username: str | None = None
        self._cookie: str | None = None
        self._tanks: dict[int, str] = {}
        self.reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Collect the Mobile Link username."""
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            self._username = username
            return await self.async_step_login_guidance()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USERNAME): str}),
            description_placeholders={"login_url": LOGIN_URL},
        )

    async def async_step_login_guidance(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Guide the user to log in and paste an authenticated cookie."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cookie = normalize_cookie_header(user_input[CONF_COOKIE_HEADER])
            if not cookie:
                errors["base"] = "invalid_auth"
            else:
                try:
                    self._tanks = await _discover_tanks(self.hass, cookie)
                except MobileLinkAuthError:
                    errors["base"] = "invalid_auth"
                except MobileLinkApiError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during Mobile Link setup")
                    errors["base"] = "cannot_connect"
                else:
                    if not self._tanks:
                        return self.async_abort(reason="no_tanks")

                    self._cookie = cookie
                    return await self.async_step_select_tanks()

        return self.async_show_form(
            step_id="login_guidance",
            data_schema=vol.Schema({vol.Required(CONF_COOKIE_HEADER): str}),
            description_placeholders={
                "login_url": LOGIN_URL,
                "username": self._username or "",
            },
            errors=errors,
        )

    async def async_step_select_tanks(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user choose which propane tanks to add."""
        errors: dict[str, str] = {}

        if not self._tanks:
            return self.async_abort(reason="no_tanks")

        if user_input is not None:
            selected = [int(value) for value in user_input[CONF_SELECTED_TANKS]]
            if not selected:
                errors["base"] = "no_tanks_selected"
            else:
                return self.async_create_entry(
                    title=f"Mobile Link ({self._username})",
                    data={
                        CONF_COOKIE_HEADER: self._cookie,
                        CONF_USERNAME: self._username,
                    },
                    options={
                        CONF_SELECTED_TANKS: selected,
                        **DEFAULT_OPTIONS,
                    },
                )

        default_selected = [str(apparatus_id) for apparatus_id in self._tanks]
        return self.async_show_form(
            step_id="select_tanks",
            data_schema=vol.Schema(
                {vol.Required(CONF_SELECTED_TANKS, default=default_selected): _tank_selector(self._tanks)}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauthentication."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._username = self.reauth_entry.data.get(CONF_USERNAME) if self.reauth_entry else None
        return await self.async_step_reauth_guidance()

    async def async_step_reauth_guidance(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Re-authenticate with a fresh cookie."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cookie = normalize_cookie_header(user_input[CONF_COOKIE_HEADER])
            if not cookie:
                errors["base"] = "invalid_auth"
            else:
                try:
                    await _discover_tanks(self.hass, cookie)
                except MobileLinkAuthError:
                    errors["base"] = "invalid_auth"
                except MobileLinkApiError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during Mobile Link reauthentication")
                    errors["base"] = "cannot_connect"
                else:
                    assert self.reauth_entry is not None
                    return self.async_update_reload_and_abort(
                        self.reauth_entry,
                        data={**self.reauth_entry.data, CONF_COOKIE_HEADER: cookie},
                    )

        return self.async_show_form(
            step_id="reauth_guidance",
            data_schema=vol.Schema({vol.Required(CONF_COOKIE_HEADER): str}),
            description_placeholders={
                "login_url": LOGIN_URL,
                "username": self._username or "",
            },
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlowHandler:
        return OptionsFlowHandler(config_entry)

    @staticmethod
    @callback
    def async_migrate_entry(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
        """Migrate older config entry schemas."""
        if config_entry.version >= 3:
            return True

        data = dict(config_entry.data)
        options = dict(config_entry.options)

        if config_entry.version < 3:
            if CONF_EMAIL in data:
                data[CONF_USERNAME] = data.pop(CONF_EMAIL)
            data.pop(CONF_PASSWORD, None)

        if CONF_SELECTED_TANKS in data:
            options.setdefault(CONF_SELECTED_TANKS, data.pop(CONF_SELECTED_TANKS))

        for key, default in DEFAULT_OPTIONS.items():
            options.setdefault(key, default)

        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            options=options,
            version=3,
        )
        return True


class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage tank selection and optional sensors."""
        errors: dict[str, str] = {}
        cookie = self.config_entry.data.get(CONF_COOKIE_HEADER, "")
        current_selected = self.config_entry.options.get(
            CONF_SELECTED_TANKS,
            self.config_entry.data.get(CONF_SELECTED_TANKS, []),
        )

        if user_input is not None:
            selected = [int(value) for value in user_input[CONF_SELECTED_TANKS]]
            if not selected:
                errors["base"] = "no_tanks_selected"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SELECTED_TANKS: selected,
                        OPT_CREATE_LAST_READING_SENSOR: user_input.get(
                            OPT_CREATE_LAST_READING_SENSOR, False
                        ),
                        OPT_CREATE_CAPACITY_SENSOR: user_input.get(
                            OPT_CREATE_CAPACITY_SENSOR, False
                        ),
                        OPT_CREATE_BATTERY_SENSOR: user_input.get(
                            OPT_CREATE_BATTERY_SENSOR, False
                        ),
                        OPT_CREATE_STATUS_SENSOR: user_input.get(
                            OPT_CREATE_STATUS_SENSOR, False
                        ),
                    },
                )

        tanks: dict[int, str] = {}
        try:
            tanks = await _discover_tanks(self.hass, cookie)
        except MobileLinkAuthError:
            errors["base"] = "invalid_auth"
        except MobileLinkApiError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error loading Mobile Link options")
            errors["base"] = "cannot_connect"

        if not tanks and not errors:
            return self.async_abort(reason="no_tanks")

        default_selected = [str(value) for value in current_selected] or [
            str(apparatus_id) for apparatus_id in tanks
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SELECTED_TANKS, default=default_selected): _tank_selector(
                        tanks
                    ),
                    vol.Optional(
                        OPT_CREATE_LAST_READING_SENSOR,
                        default=self.config_entry.options.get(
                            OPT_CREATE_LAST_READING_SENSOR, False
                        ),
                    ): bool,
                    vol.Optional(
                        OPT_CREATE_CAPACITY_SENSOR,
                        default=self.config_entry.options.get(OPT_CREATE_CAPACITY_SENSOR, False),
                    ): bool,
                    vol.Optional(
                        OPT_CREATE_BATTERY_SENSOR,
                        default=self.config_entry.options.get(OPT_CREATE_BATTERY_SENSOR, False),
                    ): bool,
                    vol.Optional(
                        OPT_CREATE_STATUS_SENSOR,
                        default=self.config_entry.options.get(OPT_CREATE_STATUS_SENSOR, False),
                    ): bool,
                }
            ),
            errors=errors,
        )
