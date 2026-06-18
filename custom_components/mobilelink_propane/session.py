from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COOKIE_UPDATED_AT,
    DEFAULT_COOKIE_LIFETIME_DAYS,
    DEFAULT_COOKIE_WARN_DAYS,
    OPT_COOKIE_LIFETIME_DAYS,
    OPT_COOKIE_WARN_DAYS,
)


def cookie_stored_at_iso() -> str:
    """Return an ISO timestamp for persisting cookie update time."""
    return dt_util.now().isoformat()


def cookie_updated_at(entry: ConfigEntry) -> datetime:
    """Return when the stored cookie was last updated."""
    raw = entry.data.get(CONF_COOKIE_UPDATED_AT)
    if isinstance(raw, str):
        parsed = dt_util.parse_datetime(raw)
        if parsed is not None:
            return parsed
    return dt_util.now()


def cookie_lifetime_days(entry: ConfigEntry) -> int:
    """Return the estimated cookie lifetime in days."""
    value = entry.options.get(OPT_COOKIE_LIFETIME_DAYS, DEFAULT_COOKIE_LIFETIME_DAYS)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_COOKIE_LIFETIME_DAYS


def cookie_warn_days(entry: ConfigEntry) -> int:
    """Return how many days before expiry to start warning."""
    value = entry.options.get(OPT_COOKIE_WARN_DAYS, DEFAULT_COOKIE_WARN_DAYS)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return DEFAULT_COOKIE_WARN_DAYS


def estimated_cookie_expiry(entry: ConfigEntry) -> datetime:
    """Return the estimated cookie expiry time."""
    return cookie_updated_at(entry) + timedelta(days=cookie_lifetime_days(entry))


def cookie_warn_at(entry: ConfigEntry) -> datetime:
    """Return when the refresh warning window begins."""
    return estimated_cookie_expiry(entry) - timedelta(days=cookie_warn_days(entry))


def cookie_age_days(entry: ConfigEntry, *, now: datetime | None = None) -> float:
    """Return how many days have passed since the cookie was stored."""
    reference = now or dt_util.now()
    delta = reference - cookie_updated_at(entry)
    return round(delta.total_seconds() / 86400, 1)


def is_cookie_refresh_due(entry: ConfigEntry, *, now: datetime | None = None) -> bool:
    """Return True when the cookie is inside the proactive refresh window."""
    reference = now or dt_util.now()
    return reference >= cookie_warn_at(entry)
