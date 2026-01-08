from __future__ import annotations

DOMAIN = "mobilelink_propane"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SELECTED_TANKS = "selected_tanks"

# Options
OPT_CREATE_LAST_READING_SENSOR = "create_last_reading_sensor"
OPT_CREATE_CAPACITY_SENSOR = "create_capacity_sensor"
OPT_CREATE_BATTERY_SENSOR = "create_battery_sensor"
OPT_CREATE_STATUS_SENSOR = "create_status_sensor"

DEFAULT_SCAN_INTERVAL_SECONDS = 300  # 5 minutes

PLATFORMS: list[str] = ["sensor"]
