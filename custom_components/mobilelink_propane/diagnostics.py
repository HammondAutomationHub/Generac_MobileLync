from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_COOKIE_HEADER


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    data = dict(entry.data)
    if CONF_COOKIE_HEADER in data:
        data[CONF_COOKIE_HEADER] = "***REDACTED***"
    return {
        "entry_data": data,
        "entry_options": dict(entry.options),
    }
