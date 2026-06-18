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
INTEGRATION_VERSION = "2.2.0"
NOTIFICATION_ID_AUTH = f"{DOMAIN}_auth_expired"
NOTIFICATION_ID_COOKIE_WARN = f"{DOMAIN}_cookie_warn"

# Config entry data
CONF_COOKIE_HEADER = "cookie_header"
CONF_COOKIE_UPDATED_AT = "cookie_updated_at"
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
OPT_COOKIE_LIFETIME_DAYS = "cookie_lifetime_days"
OPT_COOKIE_WARN_DAYS = "cookie_warn_days"

DEFAULT_COOKIE_LIFETIME_DAYS = 30
DEFAULT_COOKIE_WARN_DAYS = 3

DEFAULT_OPTIONS = {
    OPT_CREATE_LAST_READING_SENSOR: False,
    OPT_CREATE_CAPACITY_SENSOR: False,
    OPT_CREATE_BATTERY_SENSOR: False,
    OPT_CREATE_STATUS_SENSOR: False,
    OPT_COOKIE_LIFETIME_DAYS: DEFAULT_COOKIE_LIFETIME_DAYS,
    OPT_COOKIE_WARN_DAYS: DEFAULT_COOKIE_WARN_DAYS,
}

DEFAULT_SCAN_INTERVAL_SECONDS = 300  # 5 minutes

PLATFORMS = ["sensor", "binary_sensor"]
