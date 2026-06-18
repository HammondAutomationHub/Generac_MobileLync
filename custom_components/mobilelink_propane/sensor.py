from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SELECTED_TANKS,
    DOMAIN,
    OPT_CREATE_BATTERY_SENSOR,
    OPT_CREATE_CAPACITY_SENSOR,
    OPT_CREATE_LAST_READING_SENSOR,
    OPT_CREATE_STATUS_SENSOR,
)
from .coordinator import MobileLinkCoordinator
from .session import (
    cookie_age_days,
    cookie_lifetime_days,
    cookie_updated_at,
    cookie_warn_at,
    cookie_warn_days,
    estimated_cookie_expiry,
)


def _selected_tank_ids(entry: ConfigEntry, coordinator: MobileLinkCoordinator) -> list[int]:
    selected = entry.options.get(CONF_SELECTED_TANKS, entry.data.get(CONF_SELECTED_TANKS, []))
    if not selected:
        return list(coordinator.data.keys())

    selected_ids: list[int] = []
    for value in selected:
        try:
            selected_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return selected_ids or list(coordinator.data.keys())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobileLinkCoordinator = hass.data[DOMAIN][entry.entry_id]

    selected_ids = _selected_tank_ids(entry, coordinator)

    create_last = entry.options.get(OPT_CREATE_LAST_READING_SENSOR, False)
    create_capacity = entry.options.get(OPT_CREATE_CAPACITY_SENSOR, False)
    create_battery = entry.options.get(OPT_CREATE_BATTERY_SENSOR, False)
    create_status = entry.options.get(OPT_CREATE_STATUS_SENSOR, False)

    entities: list[SensorEntity] = [
        MobileLinkCookieAgeSensor(coordinator),
        MobileLinkCookieRefreshBySensor(coordinator),
    ]
    for apparatus_id in selected_ids:
        entities.append(MobileLinkPropanePercentSensor(coordinator, apparatus_id))

        if create_last:
            entities.append(MobileLinkPropaneLastReadingSensor(coordinator, apparatus_id))
        if create_capacity:
            entities.append(MobileLinkPropaneCapacitySensor(coordinator, apparatus_id))
        if create_battery:
            entities.append(MobileLinkPropaneBatterySensor(coordinator, apparatus_id))
        if create_status:
            entities.append(MobileLinkPropaneStatusSensor(coordinator, apparatus_id))

    async_add_entities(entities, update_before_add=True)


class _ServiceSensor(CoordinatorEntity[MobileLinkCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MobileLinkCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        return True


class MobileLinkCookieAgeSensor(_ServiceSensor):
    _attr_translation_key = "cookie_age"
    _attr_native_unit_of_measurement = "d"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cookie-clock"

    def __init__(self, coordinator: MobileLinkCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"mobilelink_propane_{coordinator.entry.entry_id}_cookie_age_days"

    @property
    def native_value(self) -> float:
        return cookie_age_days(self.coordinator.entry)

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        entry = self.coordinator.entry
        return {
            "cookie_updated_at": cookie_updated_at(entry).isoformat(),
            "estimated_expiry": estimated_cookie_expiry(entry).isoformat(),
            "warn_at": cookie_warn_at(entry).isoformat(),
            "estimated_lifetime_days": cookie_lifetime_days(entry),
            "warn_days_before_expiry": cookie_warn_days(entry),
        }


class MobileLinkCookieRefreshBySensor(_ServiceSensor):
    _attr_translation_key = "cookie_refresh_by"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:cookie-alert"

    def __init__(self, coordinator: MobileLinkCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"mobilelink_propane_{coordinator.entry.entry_id}_cookie_refresh_by"

    @property
    def native_value(self):
        return estimated_cookie_expiry(self.coordinator.entry)


class _BaseTankSensor(CoordinatorEntity[MobileLinkCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator)
        self._apparatus_id = int(apparatus_id)

    @property
    def _tank(self):
        return self.coordinator.data.get(self._apparatus_id)

    @property
    def device_info(self) -> DeviceInfo:
        tank = self._tank
        return DeviceInfo(
            identifiers={(DOMAIN, f"apparatus_{self._apparatus_id}")},
            via_device=(DOMAIN, self.coordinator.entry.entry_id),
            name=(tank.name if tank else f"Propane Tank {self._apparatus_id}"),
            manufacturer="Generac",
            model=(tank.device_type if tank else "Mobile Link Propane Monitor"),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._tank is not None


class _ConnectedDiagnosticSensor(_BaseTankSensor):
    @property
    def available(self) -> bool:
        tank = self._tank
        return super().available and bool(tank and tank.is_connected)


class MobileLinkPropanePercentSensor(_BaseTankSensor):
    _attr_translation_key = "propane_level"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gas-cylinder"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_percent"

    @property
    def native_value(self):
        tank = self._tank
        return tank.fuel_level if tank else None

    @property
    def extra_state_attributes(self):
        tank = self._tank
        if not tank:
            return {}
        return {
            "last_reading": tank.last_reading,
            "last_reading_at": tank.last_reading_at.isoformat() if tank.last_reading_at else None,
            "capacity_gallons": tank.capacity_gallons,
            "capacity": tank.capacity,
            "fuel_gallons": tank.fuel_gallons,
            "fuel_type": tank.fuel_type,
            "orientation": tank.orientation,
            "consumption_types": tank.consumption_types,
            "localized_address": tank.localized_address,
            "battery_level": tank.battery_level,
            "battery_percent": tank.battery_percent,
            "device_status": tank.device_status,
            "network_type": tank.network_type,
            "signal_strength": tank.signal_strength,
            "device_id": tank.device_id,
            "device_type": tank.device_type,
            "is_connected": tank.is_connected,
        }


class MobileLinkPropaneLastReadingSensor(_ConnectedDiagnosticSensor):
    _attr_translation_key = "last_reading"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_last_reading"

    @property
    def native_value(self):
        tank = self._tank
        return tank.last_reading_at if tank else None


    @property
    def available(self) -> bool:
        tank = self._tank
        return super().available and bool(tank and tank.last_reading_at is not None)


class MobileLinkPropaneCapacitySensor(_ConnectedDiagnosticSensor):
    _attr_translation_key = "capacity"
    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:storage-tank-outline"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_capacity"

    @property
    def native_value(self):
        tank = self._tank
        return tank.capacity_gallons if tank else None

    @property
    def available(self) -> bool:
        tank = self._tank
        return super().available and bool(tank and tank.capacity_gallons is not None)


class MobileLinkPropaneBatterySensor(_ConnectedDiagnosticSensor):
    """Battery sensor.

    Mobile Link often reports qualitative values such as 'good' rather than a percent.
    """

    _attr_translation_key = "battery"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:battery"

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_battery"

    @property
    def native_value(self):
        tank = self._tank
        if not tank:
            return None
        if tank.battery_percent is not None:
            return tank.battery_percent
        return tank.battery_level

    @property
    def native_unit_of_measurement(self):
        tank = self._tank
        if tank and tank.battery_percent is not None:
            return PERCENTAGE
        return None

    @property
    def device_class(self):
        tank = self._tank
        if tank and tank.battery_percent is not None:
            return SensorDeviceClass.BATTERY
        return None

    @property
    def state_class(self):
        tank = self._tank
        if tank and tank.battery_percent is not None:
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        tank = self._tank
        return tank is not None and (
            tank.battery_level is not None or tank.battery_percent is not None
        )


class MobileLinkPropaneStatusSensor(_ConnectedDiagnosticSensor):
    _attr_translation_key = "status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:access-point-network"

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_status"

    @property
    def native_value(self):
        tank = self._tank
        return tank.device_status if tank else None
