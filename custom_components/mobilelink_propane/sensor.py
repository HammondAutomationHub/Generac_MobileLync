from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    OPT_CREATE_BATTERY_SENSOR,
    OPT_CREATE_CAPACITY_SENSOR,
    OPT_CREATE_LAST_READING_SENSOR,
    OPT_CREATE_STATUS_SENSOR,
)
from .coordinator import MobileLinkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobileLinkCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for apparatus_id in coordinator.data.keys():
        entities.append(PropanePercentSensor(coordinator, entry, apparatus_id))

        if entry.options.get(OPT_CREATE_LAST_READING_SENSOR):
            entities.append(LastReadingSensor(coordinator, entry, apparatus_id))
        if entry.options.get(OPT_CREATE_CAPACITY_SENSOR):
            entities.append(CapacitySensor(coordinator, entry, apparatus_id))
        if entry.options.get(OPT_CREATE_BATTERY_SENSOR):
            entities.append(BatterySensor(coordinator, entry, apparatus_id))
        if entry.options.get(OPT_CREATE_STATUS_SENSOR):
            entities.append(StatusSensor(coordinator, entry, apparatus_id))

    async_add_entities(entities, update_before_add=True)


class _BaseTankSensor(CoordinatorEntity[MobileLinkCoordinator], SensorEntity):
    def __init__(self, coordinator: MobileLinkCoordinator, entry: ConfigEntry, apparatus_id: int) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._apparatus_id = apparatus_id

    @property
    def _tank(self):
        return self.coordinator.data.get(self._apparatus_id)

    @property
    def device_info(self) -> DeviceInfo | None:
        tank = self._tank
        if not tank:
            return None
        # Use apparatus_id as stable identifier; include device_id if available
        identifiers = {(DOMAIN, str(tank.apparatus_id))}
        if tank.device.device_id:
            identifiers.add((DOMAIN, tank.device.device_id))

        return DeviceInfo(
            identifiers=identifiers,
            name=tank.name,
            manufacturer="Generac",
            model=tank.device.device_type or "Mobile Link Propane Monitor",
        )

    @property
    def available(self) -> bool:
        tank = self._tank
        return tank is not None and (tank.is_connected is not False)


class PropanePercentSensor(_BaseTankSensor):
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:gas-cylinder"

    def __init__(self, coordinator: MobileLinkCoordinator, entry: ConfigEntry, apparatus_id: int) -> None:
        super().__init__(coordinator, entry, apparatus_id)
        self._attr_unique_id = f"{DOMAIN}_{apparatus_id}_propane_percent"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else str(self._apparatus_id)
        return f"{base} Propane"

    @property
    def native_value(self):
        tank = self._tank
        return tank.fuel_level_percent if tank else None

    @property
    def extra_state_attributes(self):
        tank = self._tank
        if not tank:
            return {}
        attrs = {
            "apparatus_id": tank.apparatus_id,
            "last_reading": tank.last_reading,
            "capacity_gallons": tank.capacity_gallons,
            "is_connected": tank.is_connected,
        }
        if tank.device:
            attrs.update(
                {
                    "device_id": tank.device.device_id,
                    "device_type": tank.device.device_type,
                    "battery_level": tank.device.battery_level,
                    "device_status": tank.device.status,
                }
            )
        return attrs


class LastReadingSensor(_BaseTankSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: MobileLinkCoordinator, entry: ConfigEntry, apparatus_id: int) -> None:
        super().__init__(coordinator, entry, apparatus_id)
        self._attr_unique_id = f"{DOMAIN}_{apparatus_id}_last_reading"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else str(self._apparatus_id)
        return f"{base} Last Reading"

    @property
    def native_value(self):
        tank = self._tank
        return tank.last_reading if tank else None


class CapacitySensor(_BaseTankSensor):
    _attr_native_unit_of_measurement = "gal"
    _attr_icon = "mdi:water"

    def __init__(self, coordinator: MobileLinkCoordinator, entry: ConfigEntry, apparatus_id: int) -> None:
        super().__init__(coordinator, entry, apparatus_id)
        self._attr_unique_id = f"{DOMAIN}_{apparatus_id}_capacity"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else str(self._apparatus_id)
        return f"{base} Capacity"

    @property
    def native_value(self):
        tank = self._tank
        if not tank or tank.capacity_gallons is None:
            return None
        try:
            return float(tank.capacity_gallons)
        except (TypeError, ValueError):
            return tank.capacity_gallons


class BatterySensor(_BaseTankSensor):
    _attr_icon = "mdi:battery"
    # battery is string like "good"/"low" — expose as text

    def __init__(self, coordinator: MobileLinkCoordinator, entry: ConfigEntry, apparatus_id: int) -> None:
        super().__init__(coordinator, entry, apparatus_id)
        self._attr_unique_id = f"{DOMAIN}_{apparatus_id}_battery"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else str(self._apparatus_id)
        return f"{base} Battery"

    @property
    def native_value(self):
        tank = self._tank
        return tank.device.battery_level if tank else None


class StatusSensor(_BaseTankSensor):
    _attr_icon = "mdi:access-point-network"

    def __init__(self, coordinator: MobileLinkCoordinator, entry: ConfigEntry, apparatus_id: int) -> None:
        super().__init__(coordinator, entry, apparatus_id)
        self._attr_unique_id = f"{DOMAIN}_{apparatus_id}_status"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else str(self._apparatus_id)
        return f"{base} Status"

    @property
    def native_value(self):
        tank = self._tank
        return tank.device.status if tank else None
