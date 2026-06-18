from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_PATH = ROOT / "custom_components" / "mobilelink_propane"
sys.path.insert(0, str(COMPONENT_PATH))

# Minimal stubs so api.py can be imported without Home Assistant installed.
aiohttp = types.ModuleType("aiohttp")


class _ClientError(Exception):
    pass


aiohttp.ClientError = _ClientError
sys.modules["aiohttp"] = aiohttp

homeassistant = types.ModuleType("homeassistant")
homeassistant_core = types.ModuleType("homeassistant.core")
homeassistant_helpers = types.ModuleType("homeassistant.helpers")
homeassistant_aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")


class _HomeAssistant:
    pass


homeassistant_core.HomeAssistant = _HomeAssistant
homeassistant_aiohttp_client.async_get_clientsession = lambda _hass: None
homeassistant.core = homeassistant_core
homeassistant.helpers = homeassistant_helpers
homeassistant_helpers.aiohttp_client = homeassistant_aiohttp_client

sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = homeassistant_core
sys.modules["homeassistant.helpers"] = homeassistant_helpers
sys.modules["homeassistant.helpers.aiohttp_client"] = homeassistant_aiohttp_client

from api import MobileLinkApiClient  # noqa: E402
from util import cookie_diagnostics, normalize_cookie_header, parse_float_value, parse_last_reading  # noqa: E402
from util import cookie_looks_incomplete, parse_cookie_dict  # noqa: E402

HAR_PROPANE_APPARATUS = {
    "apparatusId": 4967543,
    "name": "House Propane",
    "type": 2,
    "localizedAddress": "1120 Blossom Trail, Newcastle, CA, 95658",
    "isConnected": True,
    "properties": [
        {
            "name": "Device",
            "value": {
                "deviceId": "002b00293937393105473130",
                "deviceType": "lte-tankutility-v2",
                "batteryLevel": "good",
                "status": "Online",
                "networkType": "lte-tankutility-v2",
            },
        },
        {"name": "FuelType", "value": "Propane"},
        {"name": "Orientation", "value": "horizontal"},
        {"name": "Capacity", "value": "500"},
        {
            "name": "ConsumptionTypes",
            "value": "Home Heat, Water Heater, Stove/Oven, Fireplace",
        },
        {"name": "LastReading", "value": "2026-06-17T10:18:35Z"},
        {"name": "FuelLevel", "value": 50},
    ],
}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a=b; c=d", "a=b; c=d"),
        ("Cookie: a=b; c=d", "a=b; c=d"),
        ("cookie: a=b; c=d", "a=b; c=d"),
        (
            "Host: app.mobilelinkgen.com\nCookie: a=b; c=d\nAccept: */*",
            "a=b; c=d",
        ),
        (
            "curl https://app.mobilelinkgen.com -H 'Cookie: a=b; c=d'",
            "a=b; c=d",
        ),
    ],
)
def test_normalize_cookie_header(raw: str, expected: str) -> None:
    assert normalize_cookie_header(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("75", 75.0),
        ("75.5", 75.5),
        ("500", 500.0),
        ("500 gal", 500.0),
        ("1,250 gallons", 1250.0),
        ("N/A", None),
        (None, None),
    ],
)
def test_parse_float_value(raw: str | None, expected: float | None) -> None:
    assert parse_float_value(raw) == expected


def test_parse_last_reading_iso_z() -> None:
    parsed = parse_last_reading("2026-06-17T10:18:35Z")
    assert parsed == datetime(2026, 6, 17, 10, 18, 35)


@pytest.mark.parametrize(
    ("cookie", "expected_incomplete"),
    [
        ("", True),
        (".AspNetCore.Cookies=abc", False),
        (".AspNetCore.Cookies=chunks-2; .AspNetCore.CookiesC1=abc", True),
        (
            ".AspNetCore.Cookies=chunks-2; .AspNetCore.CookiesC1=abc; .AspNetCore.CookiesC2=def",
            False,
        ),
    ],
)
def test_cookie_looks_incomplete(cookie: str, expected_incomplete: bool) -> None:
    from util import cookie_looks_incomplete  # noqa: E402

    assert cookie_looks_incomplete(cookie) is expected_incomplete


def test_parse_cookie_dict_handles_chunked_aspnet_cookies() -> None:
    cookie = (
        "visid_incap_3205248=abc; .AspNetCore.Cookies=chunks-2; "
        ".AspNetCore.CookiesC1=part1; .AspNetCore.CookiesC2=part2; ai_session=x|1|2"
    )
    parsed = parse_cookie_dict(cookie)

    assert parsed[".AspNetCore.Cookies"] == "chunks-2"
    assert parsed[".AspNetCore.CookiesC1"] == "part1"
    assert parsed[".AspNetCore.CookiesC2"] == "part2"
    assert len(parsed) == 5


def test_cookie_diagnostics_reports_aspnet_parts() -> None:
    cookie = ".AspNetCore.Cookies=chunks-2; .AspNetCore.CookiesC1=a; .AspNetCore.CookiesC2=b"
    summary = cookie_diagnostics(cookie)

    assert "3 cookies parsed" in summary
    assert ".AspNetCore.Cookies" in summary
    assert ".AspNetCore.CookiesC1" in summary
    assert ".AspNetCore.CookiesC2" in summary


def test_session_cookie_refresh_window() -> None:
    from types import SimpleNamespace

    homeassistant_util_dt = types.ModuleType("homeassistant.util.dt")
    homeassistant_util = types.ModuleType("homeassistant.util")
    homeassistant_util.dt = homeassistant_util_dt
    sys.modules["homeassistant.util"] = homeassistant_util
    sys.modules["homeassistant.util.dt"] = homeassistant_util_dt

    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    homeassistant_util_dt.parse_datetime = _parse_datetime
    homeassistant_util_dt.now = lambda: datetime(2026, 6, 18, 12, 0, 0)

    from session import (  # noqa: E402
        cookie_age_days,
        cookie_warn_at,
        estimated_cookie_expiry,
        is_cookie_refresh_due,
    )

    entry = SimpleNamespace(
        data={"cookie_updated_at": "2026-06-01T12:00:00"},
        options={"cookie_lifetime_days": 30, "cookie_warn_days": 3},
    )
    now = datetime(2026, 6, 27, 12, 0, 0)

    assert cookie_age_days(entry, now=now) == 26.0
    assert estimated_cookie_expiry(entry) == datetime(2026, 7, 1, 12, 0, 0)
    assert cookie_warn_at(entry) == datetime(2026, 6, 28, 12, 0, 0)
    assert is_cookie_refresh_due(entry, now=datetime(2026, 6, 27, 12, 0, 0)) is False
    assert is_cookie_refresh_due(entry, now=datetime(2026, 6, 28, 12, 0, 0)) is True


def test_migrate_config_entry_to_version_4() -> None:
    from types import SimpleNamespace

    homeassistant_config_entries = types.ModuleType("homeassistant.config_entries")
    homeassistant_core = types.ModuleType("homeassistant.core")
    homeassistant_util_dt = types.ModuleType("homeassistant.util.dt")
    homeassistant_util = types.ModuleType("homeassistant.util")

    class _HomeAssistant:
        pass

    class _ConfigEntry:
        pass

    updates: list[dict[str, object]] = []

    def _async_update_entry(config_entry, *, data, options, version):
        updates.append({"data": data, "options": options, "version": version})
        config_entry.data = data
        config_entry.options = options
        config_entry.version = version

    homeassistant_core.HomeAssistant = _HomeAssistant
    homeassistant_config_entries.ConfigEntry = _ConfigEntry
    homeassistant_util.dt = homeassistant_util_dt
    homeassistant_util_dt.parse_datetime = lambda value: datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
    homeassistant_util_dt.now = lambda: datetime(2026, 6, 18, 12, 0, 0)

    sys.modules["homeassistant.config_entries"] = homeassistant_config_entries
    sys.modules["homeassistant.core"] = homeassistant_core
    sys.modules["homeassistant.util"] = homeassistant_util
    sys.modules["homeassistant.util.dt"] = homeassistant_util_dt

    from migrate import migrate_config_entry  # noqa: E402
    from const import CONFIG_ENTRY_VERSION  # noqa: E402

    entry = SimpleNamespace(
        version=3,
        data={"cookie_header": "a=b", "username": "user@example.com"},
        options={"selected_tanks": [1]},
    )
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_update_entry=_async_update_entry)
    )

    assert migrate_config_entry(hass, entry) is True
    assert entry.version == CONFIG_ENTRY_VERSION
    assert "cookie_updated_at" in entry.data
    assert entry.options["cookie_lifetime_days"] == 30
    assert entry.options["cookie_warn_days"] == 3
    assert len(updates) == 1


def test_parse_propane_tanks_from_har_shape() -> None:
    tanks = MobileLinkApiClient.parse_propane_tanks([HAR_PROPANE_APPARATUS])

    assert len(tanks) == 1
    tank = tanks[0]
    assert tank.apparatus_id == 4967543
    assert tank.name == "House Propane"
    assert tank.fuel_level == 50.0
    assert tank.capacity_gallons == 500.0
    assert tank.fuel_gallons == 250.0
    assert tank.battery_level == "good"
    assert tank.battery_percent is None
    assert tank.device_status == "Online"
    assert tank.device_type == "lte-tankutility-v2"
    assert tank.fuel_type == "Propane"
    assert tank.orientation == "horizontal"
    assert tank.consumption_types == "Home Heat, Water Heater, Stove/Oven, Fireplace"
    assert tank.last_reading_at == datetime(2026, 6, 17, 10, 18, 35)
