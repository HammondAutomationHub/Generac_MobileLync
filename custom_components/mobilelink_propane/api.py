from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
from aiohttp import ClientError
from homeassistant.core import HomeAssistant

from .const import (
    APPARATUS_LIST_URL,
    BROWSER_USER_AGENT,
    DASHBOARD_URL,
    LOGIN_URL,
)
from .util import parse_cookie_dict, parse_float_value, parse_last_reading

_LOGGER = logging.getLogger(__name__)


class MobileLinkAuthError(Exception):
    """Raised when auth fails (cookie invalid/expired or blocked)."""


class MobileLinkApiError(Exception):
    """Raised when the API returns an error unrelated to auth."""


@dataclass
class PropaneTank:
    apparatus_id: int
    name: str
    is_connected: bool
    device_id: str | None = None
    device_type: str | None = None
    battery_level: str | None = None
    battery_percent: float | None = None
    device_status: str | None = None
    network_type: str | None = None
    signal_strength: str | None = None
    fuel_level: float | None = None
    fuel_gallons: float | None = None
    last_reading: str | None = None
    last_reading_at: datetime | None = None
    capacity: str | None = None
    capacity_gallons: float | None = None
    fuel_type: str | None = None
    orientation: str | None = None
    consumption_types: str | None = None
    localized_address: str | None = None


def _property_string(props: dict[str, Any], name: str) -> str | None:
    value = props.get(name)
    return value if isinstance(value, str) else None


def _browser_headers(*, accept_html: bool = False) -> dict[str, str]:
    """Build browser-like headers required to pass Imperva bot protection."""
    return {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            if accept_html
            else "application/json, text/plain, */*"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": DASHBOARD_URL,
        "Origin": LOGIN_URL,
        "User-Agent": BROWSER_USER_AGENT,
        "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty" if not accept_html else "document",
        "sec-fetch-mode": "cors" if not accept_html else "navigate",
        "sec-fetch-site": "same-origin",
    }


def _looks_like_imperva_block(status: int, content_type: str, body: str) -> bool:
    lowered = body.lower()
    return status == 403 or (
        "text/html" in content_type
        and ("incapsula" in lowered or "_incapsula_" in lowered or "<html" in lowered)
    )


async def _read_response(resp: aiohttp.ClientResponse) -> tuple[str, str]:
    content_type = resp.headers.get("Content-Type", "")
    text = await resp.text()
    return content_type, text


def _raise_for_response(status: int, content_type: str, text: str) -> None:
    if _looks_like_imperva_block(status, content_type, text):
        raise MobileLinkAuthError(
            "Blocked by Imperva bot protection while Home Assistant contacted Mobile Link. "
            f"HTTP {status}. Body starts: {text[:160]!r}"
        )

    if status in (401, 403):
        raise MobileLinkAuthError(
            f"HTTP {status}: session expired or unauthorized. "
            "Copy a fresh cookie from /api/v2/Apparatus/list immediately after logging in, "
            f"then paste it right away. Body starts: {text[:160]!r}"
        )

    if status >= 500:
        raise MobileLinkApiError(f"HTTP {status}: server error. Body starts: {text[:160]!r}")

    if status >= 400:
        raise MobileLinkApiError(f"HTTP {status}: request failed. Body starts: {text[:160]!r}")

    if "application/json" not in content_type:
        raise MobileLinkAuthError(
            f"Expected JSON but got {content_type or 'unknown content-type'}. "
            f"Body starts: {text[:160]!r}"
        )


class MobileLinkApiClient:
    """Minimal Mobile Link client using a user-provided authenticated cookie header."""

    BASE = "https://app.mobilelinkgen.com"

    def __init__(self, hass: HomeAssistant) -> None:
        """Accept hass for compatibility with the coordinator."""

    async def get_apparatus_list(self, cookie_header: str) -> list[dict[str, Any]]:
        cookies = parse_cookie_dict(cookie_header)
        if not cookies:
            raise MobileLinkAuthError("No cookies were parsed from the pasted value.")

        _LOGGER.debug(
            "Contacting Mobile Link with %d cookies, total header length %d",
            len(cookies),
            len(cookie_header),
        )

        timeout = aiohttp.ClientTimeout(total=45)
        jar = aiohttp.CookieJar(unsafe=True)
        jar.update_cookies(cookies)

        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                cookie_jar=jar,
                headers={"User-Agent": BROWSER_USER_AGENT},
            ) as session:
                # Refresh Imperva/session cookies from Home Assistant's outbound IP.
                async with session.get(
                    DASHBOARD_URL,
                    headers=_browser_headers(accept_html=True),
                    allow_redirects=True,
                ) as warmup_resp:
                    warmup_type, warmup_body = await _read_response(warmup_resp)
                    _LOGGER.debug(
                        "Mobile Link dashboard warmup returned HTTP %s (%s)",
                        warmup_resp.status,
                        warmup_type or "unknown",
                    )
                    if _looks_like_imperva_block(
                        warmup_resp.status, warmup_type, warmup_body
                    ):
                        raise MobileLinkAuthError(
                            "Blocked by Imperva during dashboard warmup. "
                            f"HTTP {warmup_resp.status}. Body starts: {warmup_body[:160]!r}"
                        )

                async with session.get(
                    APPARATUS_LIST_URL,
                    headers=_browser_headers(),
                ) as resp:
                    content_type, text = await _read_response(resp)
                    _raise_for_response(resp.status, content_type, text)

                    try:
                        data = await resp.json(content_type=None)
                    except Exception as err:
                        raise MobileLinkApiError(
                            f"Failed to parse JSON. Body starts: {text[:160]!r}"
                        ) from err
        except ClientError as err:
            raise MobileLinkApiError(f"Connection error: {err}") from err

        if not isinstance(data, list):
            raise MobileLinkApiError(f"Unexpected apparatus list shape: {type(data)}")
        return data

    @staticmethod
    def parse_propane_tanks(apparatus_list: list[dict[str, Any]]) -> list[PropaneTank]:
        tanks: list[PropaneTank] = []
        for apparatus in apparatus_list:
            if apparatus.get("type") != 2:
                continue

            props = {
                prop.get("name"): prop.get("value")
                for prop in apparatus.get("properties", [])
                if isinstance(prop, dict)
            }
            device = props.get("Device") if isinstance(props.get("Device"), dict) else {}

            fuel_level = parse_float_value(props.get("FuelLevel"))
            last_reading_raw = props.get("LastReading")
            last_reading = str(last_reading_raw) if last_reading_raw is not None else None
            capacity_raw = props.get("Capacity")
            capacity = str(capacity_raw) if capacity_raw is not None else None
            capacity_gallons = parse_float_value(capacity_raw)
            battery_level_raw = device.get("batteryLevel") if isinstance(device, dict) else None
            battery_level = (
                str(battery_level_raw) if battery_level_raw is not None else None
            )
            fuel_gallons = None
            if capacity_gallons is not None and fuel_level is not None:
                fuel_gallons = round(capacity_gallons * fuel_level / 100, 1)

            tanks.append(
                PropaneTank(
                    apparatus_id=int(apparatus.get("apparatusId")),
                    name=str(
                        apparatus.get("name") or f"Propane Tank {apparatus.get('apparatusId')}"
                    ),
                    is_connected=bool(apparatus.get("isConnected", False)),
                    localized_address=(
                        apparatus.get("localizedAddress")
                        if isinstance(apparatus.get("localizedAddress"), str)
                        else None
                    ),
                    device_id=(device.get("deviceId") if isinstance(device, dict) else None),
                    device_type=(device.get("deviceType") if isinstance(device, dict) else None),
                    battery_level=battery_level,
                    battery_percent=parse_float_value(battery_level_raw),
                    device_status=(device.get("status") if isinstance(device, dict) else None),
                    network_type=(device.get("networkType") if isinstance(device, dict) else None),
                    signal_strength=(
                        str(device.get("signalStrength"))
                        if isinstance(device, dict) and device.get("signalStrength") is not None
                        else None
                    ),
                    fuel_level=fuel_level,
                    fuel_gallons=fuel_gallons,
                    last_reading=last_reading,
                    last_reading_at=parse_last_reading(last_reading),
                    capacity=capacity,
                    capacity_gallons=capacity_gallons,
                    fuel_type=_property_string(props, "FuelType"),
                    orientation=_property_string(props, "Orientation"),
                    consumption_types=_property_string(props, "ConsumptionTypes"),
                )
            )
        return tanks
