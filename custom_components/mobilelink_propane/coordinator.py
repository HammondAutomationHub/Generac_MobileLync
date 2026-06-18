from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.components import persistent_notification
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MobileLinkApiClient, MobileLinkAuthError, MobileLinkApiError, PropaneTank
from .const import (
    CONF_COOKIE_HEADER,
    CONF_SELECTED_TANKS,
    DOMAIN,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    NOTIFICATION_ID_AUTH,
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

    def _notification_id(self) -> str:
        return f"{NOTIFICATION_ID_AUTH}_{self.entry.entry_id}"

    def _selected_ids(self) -> set[int]:
        selected = self.entry.options.get(
            CONF_SELECTED_TANKS,
            self.entry.data.get(CONF_SELECTED_TANKS, []),
        )
        if not selected:
            return set()

        selected_ids: set[int] = set()
        for value in selected:
            try:
                selected_ids.add(int(value))
            except (TypeError, ValueError):
                _LOGGER.warning("Ignoring invalid selected tank id: %r", value)
        return selected_ids

    def _dismiss_auth_notification(self) -> None:
        persistent_notification.async_dismiss(self.hass, self._notification_id())

    def _notify_auth_expired(self) -> None:
        persistent_notification.async_create(
            self.hass,
            (
                "Your Mobile Link session has expired. Open **Settings → Devices & Services**, "
                "select **Generac Mobile Link Propane**, and choose **Reconfigure** to paste a "
                "fresh cookie."
            ),
            title="Mobile Link session expired",
            notification_id=self._notification_id(),
        )

    async def _async_update_data(self) -> dict[int, PropaneTank]:
        cookie_header = self.entry.data.get(CONF_COOKIE_HEADER)
        if not cookie_header:
            self._notify_auth_expired()
            raise ConfigEntryAuthFailed("No cookie header configured")

        try:
            apparatus = await self.client.get_apparatus_list(cookie_header)
            tanks = self.client.parse_propane_tanks(apparatus)
            selected = self._selected_ids()
            if selected:
                tanks = [tank for tank in tanks if tank.apparatus_id in selected]
            self._dismiss_auth_notification()
            return {tank.apparatus_id: tank for tank in tanks}
        except MobileLinkAuthError as err:
            self._notify_auth_expired()
            raise ConfigEntryAuthFailed(str(err)) from err
        except MobileLinkApiError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err
