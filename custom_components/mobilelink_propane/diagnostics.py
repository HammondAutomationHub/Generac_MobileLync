from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, DOMAIN
from .coordinator import MobileLinkCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    coordinator: MobileLinkCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Redact secrets
    redacted_data = dict(entry.data)
    if CONF_PASSWORD in redacted_data:
        redacted_data[CONF_PASSWORD] = "***REDACTED***"

    tanks = {}
    for k, v in coordinator.data.items():
        tanks[str(k)] = {
            "apparatus_id": v.apparatus_id,
            "name": v.name,
            "fuel_level_percent": v.fuel_level_percent,
            "last_reading": v.last_reading,
            "capacity_gallons": v.capacity_gallons,
            "is_connected": v.is_connected,
            "device": {
                "device_id": v.device.device_id,
                "device_type": v.device.device_type,
                "battery_level": v.device.battery_level,
                "status": v.device.status,
            },
        }

    return {
        "entry_data": redacted_data,
        "entry_options": dict(entry.options),
        "tanks": tanks,
    }
