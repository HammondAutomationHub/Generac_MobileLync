from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .api import MobileLinkApiClient, MobileLinkAuthError
from .const import (
    DOMAIN,
    CONF_COOKIE_HEADER,
    CONF_SELECTED_TANKS,
    OPT_CREATE_LAST_READING_SENSOR,
    OPT_CREATE_CAPACITY_SENSOR,
    OPT_CREATE_BATTERY_SENSOR,
    OPT_CREATE_STATUS_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


STEP_COOKIE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COOKIE_HEADER): str,
    }
)


def _tank_select_schema(tank_map: dict[str, str]) -> vol.Schema:
    return vol.Schema({vol.Required(CONF_SELECTED_TANKS): vol.In(tank_map, multiple=True)})


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(OPT_CREATE_LAST_READING_SENSOR, default=False): bool,
        vol.Optional(OPT_CREATE_CAPACITY_SENSOR, default=False): bool,
        vol.Optional(OPT_CREATE_BATTERY_SENSOR, default=False): bool,
        vol.Optional(OPT_CREATE_STATUS_SENSOR, default=False): bool,
    }
)



def _extract_cookie_value(cookie_input: str) -> str:
    """Extract the cookie header value from a pasted string.

    Accepts any of:
    - raw cookie value: "a=b; c=d"
    - a header line: "Cookie: a=b; c=d"
    - a full header block that includes a Cookie line
    - a curl command containing -H 'Cookie: ...'
    """
    raw = (cookie_input or "").strip()

    # If user pasted a curl command, extract the Cookie header inside -H / --header
    m = re.search(r"(?:-H|--header)\s+['\"]?Cookie\s*:\s*([^'\"\n\r]+)['\"]?", raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # If user pasted a header block, find the Cookie: line
    m = re.search(r"^Cookie\s*:\s*(.+)$", raw, re.IGNORECASE | re.MULTILINE)
    if m:
        return m.group(1).strip()

    # If user pasted a request headers section that contains "cookie:" in the middle
    m = re.search(r"\bcookie\s*:\s*([^\n\r]+)", raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Otherwise assume they pasted the cookie value
    return raw.strip(" \t\r\n\"'")


async def _fetch_tanks(hass: HomeAssistant, cookie_header: str) -> dict[str, str]:
    client = MobileLinkApiClient(hass)
    apparatus = await client.get_apparatus_list(cookie_header)
    tanks = client.parse_propane_tanks(apparatus)
    # Map id->name (string keys for vol.In)
    return {str(t.apparatus_id): t.name for t in tanks}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._cookie_header: str | None = None
        self._tank_map: dict[str, str] | None = None
        self._error_detail: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            cookie_header = _extract_cookie_value(user_input[CONF_COOKIE_HEADER])
            try:
                tank_map = await _fetch_tanks(self.hass, cookie_header)
                if not tank_map:
                    self._error_detail = "No propane tanks were found in your account."
                    errors["base"] = "no_tanks"
                else:
                    self._cookie_header = cookie_header
                    self._tank_map = tank_map
                    await self.async_set_unique_id(f"mobilelink_cookie_{hash(cookie_header)}")
                    return await self.async_step_select_tanks()
            except MobileLinkAuthError as e:
                self._error_detail = str(e)
                errors["base"] = "invalid_cookie"
            except Exception as e:
                self._error_detail = str(e)
                errors["base"] = "cannot_connect"

        description_placeholders = {"error_detail": self._error_detail or ""}

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_COOKIE_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_select_tanks(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        assert self._cookie_header is not None
        assert self._tank_map is not None

        if user_input is not None:
            selected = [int(x) for x in user_input[CONF_SELECTED_TANKS]]
            data = {
                CONF_COOKIE_HEADER: self._cookie_header,
                CONF_SELECTED_TANKS: selected,
            }
            # Default options: all optional sensors off
            options = {
                OPT_CREATE_LAST_READING_SENSOR: False,
                OPT_CREATE_CAPACITY_SENSOR: False,
                OPT_CREATE_BATTERY_SENSOR: False,
                OPT_CREATE_STATUS_SENSOR: False,
                CONF_SELECTED_TANKS: selected,
            }
            return self.async_create_entry(title="Mobile Link Propane", data=data, options=options)

        return self.async_show_form(
            step_id="select_tanks",
            data_schema=_tank_select_schema(self._tank_map),
            errors=errors,
        )

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self._error_detail = "Your Mobile Link session cookie is invalid or expired. Paste a fresh cookie header."
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            cookie_header = _extract_cookie_value(user_input[CONF_COOKIE_HEADER])
            try:
                tank_map = await _fetch_tanks(self.hass, cookie_header)
                if not tank_map:
                    self._error_detail = "No propane tanks were found in your account."
                    errors["base"] = "no_tanks"
                else:
                    entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
                    assert entry is not None
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_COOKIE_HEADER: cookie_header},
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
            except MobileLinkAuthError as e:
                self._error_detail = str(e)
                errors["base"] = "invalid_cookie"
            except Exception as e:
                self._error_detail = str(e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_COOKIE_SCHEMA,
            errors=errors,
            description_placeholders={"error_detail": self._error_detail or ""},
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._tank_map: dict[str, str] | None = None
        self._error_detail: str | None = None

    async def async_step_init(self, user_input=None) -> FlowResult:
        # Step 1: refresh tank list using current cookie
        cookie_header = self.config_entry.data.get(CONF_COOKIE_HEADER, "")
        try:
            self._tank_map = await _fetch_tanks(self.hass, cookie_header)
        except Exception as e:
            _LOGGER.warning("Failed to refresh tank list for options: %s", e)
            self._tank_map = None

        return await self.async_step_select_tanks()

    async def async_step_select_tanks(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}

        tank_map = self._tank_map
        if not tank_map:
            # If we couldn't refresh, fall back to stored IDs
            current = self.config_entry.options.get(CONF_SELECTED_TANKS, self.config_entry.data.get(CONF_SELECTED_TANKS, []))
            tank_map = {str(i): f"Tank {i}" for i in current} or {"0": "No tanks found"}

        if user_input is not None:
            selected = [int(x) for x in user_input[CONF_SELECTED_TANKS]]
            # move to sensor toggles
            self._selected = selected
            return await self.async_step_sensors()

        current_selected = self.config_entry.options.get(CONF_SELECTED_TANKS, self.config_entry.data.get(CONF_SELECTED_TANKS, []))
        schema = vol.Schema(
            {
                vol.Required(CONF_SELECTED_TANKS, default=[str(i) for i in current_selected]): vol.In(tank_map, multiple=True),
            }
        )
        return self.async_show_form(step_id="select_tanks", data_schema=schema, errors=errors)

    async def async_step_sensors(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        defaults = {
            OPT_CREATE_LAST_READING_SENSOR: self.config_entry.options.get(OPT_CREATE_LAST_READING_SENSOR, False),
            OPT_CREATE_CAPACITY_SENSOR: self.config_entry.options.get(OPT_CREATE_CAPACITY_SENSOR, False),
            OPT_CREATE_BATTERY_SENSOR: self.config_entry.options.get(OPT_CREATE_BATTERY_SENSOR, False),
            OPT_CREATE_STATUS_SENSOR: self.config_entry.options.get(OPT_CREATE_STATUS_SENSOR, False),
        }
        schema = vol.Schema(
            {
                vol.Optional(OPT_CREATE_LAST_READING_SENSOR, default=defaults[OPT_CREATE_LAST_READING_SENSOR]): bool,
                vol.Optional(OPT_CREATE_CAPACITY_SENSOR, default=defaults[OPT_CREATE_CAPACITY_SENSOR]): bool,
                vol.Optional(OPT_CREATE_BATTERY_SENSOR, default=defaults[OPT_CREATE_BATTERY_SENSOR]): bool,
                vol.Optional(OPT_CREATE_STATUS_SENSOR, default=defaults[OPT_CREATE_STATUS_SENSOR]): bool,
            }
        )

        if user_input is not None:
            options = {**user_input, CONF_SELECTED_TANKS: getattr(self, "_selected", [])}
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(step_id="sensors", data_schema=schema, errors=errors)
