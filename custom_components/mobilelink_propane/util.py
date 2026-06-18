from __future__ import annotations

import re
from datetime import datetime

_COOKIE_PREFIX_RE = re.compile(r"^cookie\s*:\s*", re.IGNORECASE)
_CURL_COOKIE_RE = re.compile(
    r"""-H\s+['"]Cookie:\s*([^'"]+)['"]""",
    re.IGNORECASE,
)


def normalize_cookie_header(value: str) -> str:
    """Normalize pasted cookie values from DevTools, header blocks, or curl commands."""
    value = value.strip()
    if not value:
        return value

    # Collapse accidental line breaks from copy/paste.
    value = value.replace("\r\n", "").replace("\n", "").replace("\r", "")
    value = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", value)

    curl_match = _CURL_COOKIE_RE.search(value)
    if curl_match:
        return curl_match.group(1).strip()

    for line in value.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("cookie:"):
            return _COOKIE_PREFIX_RE.sub("", line).strip()

    return _COOKIE_PREFIX_RE.sub("", value).strip()


def parse_cookie_dict(cookie_header: str) -> dict[str, str]:
    """Parse a Cookie request header into a name/value mapping."""
    cookies: dict[str, str] = {}
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name:
            cookies[name] = value
    return cookies


def cookie_looks_incomplete(cookie_header: str) -> bool:
    """Return True when required Mobile Link auth cookie parts appear to be missing."""
    cookie = cookie_header.strip()
    if not cookie:
        return True

    if ".AspNetCore.Cookies" not in cookie:
        return True

    if ".AspNetCore.Cookies=chunks" in cookie:
        if ".AspNetCore.CookiesC1=" not in cookie:
            return True
        if "chunks-2" in cookie and ".AspNetCore.CookiesC2=" not in cookie:
            return True

    return False


def parse_last_reading(value: str | None) -> datetime | None:
    """Parse Mobile Link last-reading timestamps into datetimes."""
    if not value:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        pass

    for fmt in (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    return None


def parse_float_value(value: str | float | int | None) -> float | None:
    """Parse numeric API values that may include units or formatting."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).strip()
    if not cleaned:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", cleaned.replace(",", ""))
    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None
