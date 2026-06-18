from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import APPARATUS_LIST_URL, INTEGRATION_VERSION, LOGIN_URL
from .util import parse_float_value, parse_last_reading


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


class MobileLinkApiClient:
    """Minimal Mobile Link client using a user-provided authenticated cookie header."""

    BASE = "https://app.mobilelinkgen.com"

    def __init__(self, hass: HomeAssistant) -> None:
        self._session = async_get_clientsession(hass)

    async def get_apparatus_list(self, cookie_header: str) -> list[dict[str, Any]]:
        headers = {
            "Cookie": cookie_header,
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{LOGIN_URL}/dashboard",
            "User-Agent": f"HomeAssistant-MobileLinkPropane/{INTEGRATION_VERSION}",
        }

        try:
            resp = await self._session.get(APPARATUS_LIST_URL, headers=headers)
        except ClientError as err:
            raise MobileLinkApiError(f"Connection error: {err}") from err

        if resp.status in (401, 403):
            text = await resp.text()
            raise MobileLinkAuthError(
                f"HTTP {resp.status}: unauthorized/forbidden. Body starts: {text[:120]!r}"
            )

        if resp.status >= 500:
            text = await resp.text()
            raise MobileLinkApiError(
                f"HTTP {resp.status}: server error. Body starts: {text[:120]!r}"
            )

        if resp.status >= 400:
            text = await resp.text()
            raise MobileLinkApiError(
                f"HTTP {resp.status}: request failed. Body starts: {text[:120]!r}"
            )

        content_type = resp.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            text = await resp.text()
            # Non-JSON usually means login page HTML or bot protection.
            raise MobileLinkAuthError(
                f"Expected JSON but got {content_type or 'unknown content-type'}. "
                f"Body starts: {text[:120]!r}"
            )

        try:
            data = await resp.json()
        except Exception as err:
            text = await resp.text()
            raise MobileLinkApiError(
                f"Failed to parse JSON. Body starts: {text[:120]!r}"
            ) from err

        if not isinstance(data, list):
            raise MobileLinkApiError(f"Unexpected apparatus list shape: {type(data)}")
        return data

    @staticmethod
    def parse_propane_tanks(apparatus_list: list[dict[str, Any]]) -> list[PropaneTank]:
        tanks: list[PropaneTank] = []
        for apparatus in apparatus_list:
            # type == 2 is a fuel monitor / propane tank (confirmed via HAR capture).
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
