from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobileLinkCoordinator
from .session import is_cookie_refresh_due


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobileLinkCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MobileLinkCookieRefreshDueBinarySensor(coordinator)])


class MobileLinkCookieRefreshDueBinarySensor(
    CoordinatorEntity[MobileLinkCoordinator], BinarySensorEntity
):
    _attr_translation_key = "cookie_refresh_due"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MobileLinkCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"mobilelink_propane_{coordinator.entry.entry_id}_cookie_refresh_due"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
        )

    @property
    def is_on(self) -> bool:
        return is_cookie_refresh_due(self.coordinator.entry)

    @property
    def available(self) -> bool:
        return True
