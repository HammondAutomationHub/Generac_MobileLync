from __future__ import annotations

DOMAIN = "mobilelink_propane"

LOGIN_URL = "https://app.mobilelinkgen.com"
APPARATUS_LIST_URL = f"{LOGIN_URL}/api/v2/Apparatus/list"
DASHBOARD_URL = f"{LOGIN_URL}/dashboard"

# Mobile Link sits behind Imperva and rejects non-browser user agents (403 HTML).
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)
INTEGRATION_VERSION = "2.1.5"
NOTIFICATION_ID_AUTH = f"{DOMAIN}_auth_expired"

# Config entry data
CONF_COOKIE_HEADER = "cookie_header"
CONF_USERNAME = "username"
CONF_SELECTED_TANKS = "selected_tanks"

# Legacy v1 keys (migration only)
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# Options
OPT_CREATE_LAST_READING_SENSOR = "create_last_reading_sensor"
OPT_CREATE_CAPACITY_SENSOR = "create_capacity_sensor"
OPT_CREATE_BATTERY_SENSOR = "create_battery_sensor"
OPT_CREATE_STATUS_SENSOR = "create_status_sensor"

DEFAULT_OPTIONS = {
    OPT_CREATE_LAST_READING_SENSOR: False,
    OPT_CREATE_CAPACITY_SENSOR: False,
    OPT_CREATE_BATTERY_SENSOR: False,
    OPT_CREATE_STATUS_SENSOR: False,
}

DEFAULT_SCAN_INTERVAL_SECONDS = 300  # 5 minutes

PLATFORMS = ["sensor"]
