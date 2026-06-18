from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import INTEGRATION_VERSION
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
    fuel_level: float | None = None
    last_reading: str | None = None
    last_reading_at: datetime | None = None
    capacity: str | None = None
    capacity_gallons: float | None = None


class MobileLinkApiClient:
    """Minimal Mobile Link client using a user-provided authenticated cookie header."""

    BASE = "https://app.mobilelinkgen.com"

    def __init__(self, hass: HomeAssistant) -> None:
        self._session = async_get_clientsession(hass)

    async def get_apparatus_list(self, cookie_header: str) -> list[dict[str, Any]]:
        headers = {
            "Cookie": cookie_header,
            "Accept": "application/json, text/plain, */*",
            "User-Agent": f"HomeAssistant-MobileLinkPropane/{INTEGRATION_VERSION}",
        }

        try:
            resp = await self._session.get(
                f"{self.BASE}/api/v2/Apparatus/list",
                headers=headers,
            )
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
            # type == 2 appears to be propane apparatus (per HAR)
            if apparatus.get("type") != 2:
                continue

            props = {
                prop.get("name"): prop.get("value")
                for prop in apparatus.get("properties", [])
                if isinstance(prop, dict)
            }
            device = props.get("Device") if isinstance(props.get("Device"), dict) else {}

            fuel_level = parse_float_value(props.get("FuelLevel"))
            last_reading = (
                props.get("LastReading") if isinstance(props.get("LastReading"), str) else None
            )
            capacity_raw = props.get("Capacity")
            capacity = str(capacity_raw) if capacity_raw is not None else None
            battery_level = (
                device.get("batteryLevel") if isinstance(device, dict) else None
            )

            tanks.append(
                PropaneTank(
                    apparatus_id=int(apparatus.get("apparatusId")),
                    name=str(
                        apparatus.get("name") or f"Propane Tank {apparatus.get('apparatusId')}"
                    ),
                    is_connected=bool(apparatus.get("isConnected", False)),
                    device_id=(device.get("deviceId") if isinstance(device, dict) else None),
                    device_type=(device.get("deviceType") if isinstance(device, dict) else None),
                    battery_level=(
                        str(battery_level) if battery_level is not None else None
                    ),
                    battery_percent=parse_float_value(battery_level),
                    device_status=(device.get("status") if isinstance(device, dict) else None),
                    fuel_level=fuel_level,
                    last_reading=last_reading,
                    last_reading_at=parse_last_reading(last_reading),
                    capacity=capacity,
                    capacity_gallons=parse_float_value(capacity_raw),
                )
            )
        return tanks
