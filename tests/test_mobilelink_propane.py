from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_PATH = ROOT / "custom_components" / "mobilelink_propane"
sys.path.insert(0, str(COMPONENT_PATH))

from util import normalize_cookie_header, parse_float_value, parse_last_reading  # noqa: E402


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
        ("500 gal", 500.0),
        ("1,250 gallons", 1250.0),
        ("N/A", None),
        (None, None),
    ],
)
def test_parse_float_value(raw: str | None, expected: float | None) -> None:
    assert parse_float_value(raw) == expected


def test_parse_last_reading_iso() -> None:
    parsed = parse_last_reading("2024-06-18T14:30:00")
    assert parsed == datetime(2024, 6, 18, 14, 30, 0)


def test_parse_last_reading_us_format() -> None:
    parsed = parse_last_reading("06/18/2024 02:30:00 PM")
    assert parsed == datetime(2024, 6, 18, 14, 30, 0)
