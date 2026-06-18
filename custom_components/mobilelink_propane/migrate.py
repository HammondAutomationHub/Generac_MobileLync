from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_COOKIE_UPDATED_AT,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SELECTED_TANKS,
    CONF_USERNAME,
    CONFIG_ENTRY_VERSION,
    DEFAULT_OPTIONS,
)
from .session import cookie_stored_at_iso

_LOGGER = logging.getLogger(__name__)


def migrate_config_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate a config entry to the current schema version."""
    if config_entry.version > CONFIG_ENTRY_VERSION:
        _LOGGER.error(
            "Cannot downgrade Mobile Link config entry from version %s",
            config_entry.version,
        )
        return False

    data = dict(config_entry.data)
    options = dict(config_entry.options)
    version = config_entry.version
    changed = False

    if version < 3:
        if CONF_EMAIL in data:
            data[CONF_USERNAME] = data.pop(CONF_EMAIL)
            changed = True
        if CONF_PASSWORD in data:
            data.pop(CONF_PASSWORD, None)
            changed = True

        if CONF_SELECTED_TANKS in data:
            options.setdefault(CONF_SELECTED_TANKS, data.pop(CONF_SELECTED_TANKS))
            changed = True

    if version < CONFIG_ENTRY_VERSION:
        changed = True

    if CONF_COOKIE_UPDATED_AT not in data:
        data[CONF_COOKIE_UPDATED_AT] = cookie_stored_at_iso()
        changed = True

    for key, default in DEFAULT_OPTIONS.items():
        if key not in options:
            options[key] = default
            changed = True

    if version < CONFIG_ENTRY_VERSION:
        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            options=options,
            version=CONFIG_ENTRY_VERSION,
        )
        _LOGGER.info(
            "Migrated Mobile Link config entry from version %s to %s",
            version,
            CONFIG_ENTRY_VERSION,
        )
        return True

    if changed:
        hass.config_entries.async_update_entry(
            config_entry,
            data=data,
            options=options,
        )
        _LOGGER.info("Repaired Mobile Link config entry data for version %s", version)

    return True
