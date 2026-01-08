from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MobileLinkApiClient, MobileLinkAuthError, MobileLinkApiError, PropaneTank
from .const import (
    CONF_COOKIE_HEADER,
    CONF_SELECTED_TANKS,
    DOMAIN,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class MobileLinkCoordinator(DataUpdateCoordinator[dict[int, PropaneTank]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.client = MobileLinkApiClient(hass)

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )

    def _selected_ids(self) -> set[int]:
        # Prefer options if present, otherwise fall back to entry.data
        selected = self.entry.options.get(CONF_SELECTED_TANKS, self.entry.data.get(CONF_SELECTED_TANKS, []))
        try:
            return {int(x) for x in selected}
        except Exception:
            return set()

    async def _async_update_data(self) -> dict[int, PropaneTank]:
        cookie_header = self.entry.data.get(CONF_COOKIE_HEADER)
        if not cookie_header:
            raise ConfigEntryAuthFailed("No cookie header configured")

        try:
            apparatus = await self.client.get_apparatus_list(cookie_header)
            tanks = self.client.parse_propane_tanks(apparatus)
            selected = self._selected_ids()
            if selected:
                tanks = [t for t in tanks if t.apparatus_id in selected]
            return {t.apparatus_id: t for t in tanks}
        except MobileLinkAuthError as e:
            # Triggers Reauth flow in HA
            raise ConfigEntryAuthFailed(str(e)) from e
        except MobileLinkApiError as e:
            raise UpdateFailed(str(e)) from e
        except Exception as e:
            raise UpdateFailed(f"Unexpected error: {e}") from e
