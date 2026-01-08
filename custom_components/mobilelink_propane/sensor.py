from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_SELECTED_TANKS,
    OPT_CREATE_LAST_READING_SENSOR,
    OPT_CREATE_CAPACITY_SENSOR,
    OPT_CREATE_BATTERY_SENSOR,
    OPT_CREATE_STATUS_SENSOR,
)
from .coordinator import MobileLinkCoordinator


@dataclass(frozen=True)
class _TankRef:
    apparatus_id: int


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: MobileLinkCoordinator = hass.data[DOMAIN][entry.entry_id]

    selected = entry.options.get(CONF_SELECTED_TANKS, entry.data.get(CONF_SELECTED_TANKS, []))
    selected_ids = [int(x) for x in selected] if selected else list(coordinator.data.keys())

    create_last = entry.options.get(OPT_CREATE_LAST_READING_SENSOR, False)
    create_capacity = entry.options.get(OPT_CREATE_CAPACITY_SENSOR, False)
    create_battery = entry.options.get(OPT_CREATE_BATTERY_SENSOR, False)
    create_status = entry.options.get(OPT_CREATE_STATUS_SENSOR, False)

    entities: list[SensorEntity] = []
    for aid in selected_ids:
        entities.append(MobileLinkPropanePercentSensor(coordinator, aid))

        if create_last:
            entities.append(MobileLinkPropaneLastReadingSensor(coordinator, aid))
        if create_capacity:
            entities.append(MobileLinkPropaneCapacitySensor(coordinator, aid))
        if create_battery:
            entities.append(MobileLinkPropaneBatterySensor(coordinator, aid))
        if create_status:
            entities.append(MobileLinkPropaneStatusSensor(coordinator, aid))

    async_add_entities(entities, update_before_add=True)


class _BaseTankSensor(CoordinatorEntity[MobileLinkCoordinator], SensorEntity):
    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator)
        self._apparatus_id = int(apparatus_id)

    @property
    def _tank(self):
        return self.coordinator.data.get(self._apparatus_id)

    @property
    def device_info(self) -> DeviceInfo:
        tank = self._tank
        identifiers = {(DOMAIN, f"apparatus_{self._apparatus_id}")}
        return DeviceInfo(
            identifiers=identifiers,
            name=(tank.name if tank else f"Propane Tank {self._apparatus_id}"),
            manufacturer="Generac",
            model=(tank.device_type if tank else "Mobile Link Apparatus"),
        )

    @property
    def available(self) -> bool:
        tank = self._tank
        if tank is None:
            return False
        return True


class MobileLinkPropanePercentSensor(_BaseTankSensor):
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:gas-cylinder"

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_percent"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else f"Tank {self._apparatus_id}"
        return f"{base} Propane"

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
            "capacity_gallons": tank.capacity,
            "battery_level": tank.battery_level,
            "device_status": tank.device_status,
            "device_id": tank.device_id,
            "device_type": tank.device_type,
            "is_connected": tank.is_connected,
        }


class MobileLinkPropaneLastReadingSensor(_BaseTankSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_last_reading"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else f"Tank {self._apparatus_id}"
        return f"{base} Last Reading"

    @property
    def native_value(self):
        tank = self._tank
        return tank.last_reading if tank else None


class MobileLinkPropaneCapacitySensor(_BaseTankSensor):
    _attr_icon = "mdi:storage-tank-outline"
    _attr_native_unit_of_measurement = "gal"

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_capacity"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else f"Tank {self._apparatus_id}"
        return f"{base} Capacity"

    @property
    def native_value(self):
        tank = self._tank
        return tank.capacity if tank else None


class MobileLinkPropaneBatterySensor(_BaseTankSensor):
    _attr_icon = "mdi:battery"

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_battery"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else f"Tank {self._apparatus_id}"
        return f"{base} Battery"

    @property
    def native_value(self):
        tank = self._tank
        return tank.battery_level if tank else None


class MobileLinkPropaneStatusSensor(_BaseTankSensor):
    _attr_icon = "mdi:access-point-network"

    def __init__(self, coordinator: MobileLinkCoordinator, apparatus_id: int) -> None:
        super().__init__(coordinator, apparatus_id)
        self._attr_unique_id = f"mobilelink_propane_{apparatus_id}_status"

    @property
    def name(self) -> str:
        tank = self._tank
        base = tank.name if tank else f"Tank {self._apparatus_id}"
        return f"{base} Status"

    @property
    def native_value(self):
        tank = self._tank
        return tank.device_status if tank else None
