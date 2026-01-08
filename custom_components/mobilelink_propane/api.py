from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientResponseError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


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
    device_status: str | None = None
    fuel_level: float | None = None
    last_reading: str | None = None
    capacity: str | None = None


class MobileLinkApiClient:
    """Minimal Mobile Link client using a user-provided authenticated cookie header."""

    BASE = "https://app.mobilelinkgen.com"

    def __init__(self, hass: HomeAssistant) -> None:
        self._session = async_get_clientsession(hass)

    async def get_apparatus_list(self, cookie_header: str) -> list[dict[str, Any]]:
        headers = {
            "Cookie": cookie_header,
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "HomeAssistant-MobileLinkPropane/1.0",
        }

        try:
            resp = await self._session.get(f"{self.BASE}/api/v2/Apparatus/list", headers=headers)
        except ClientResponseError as e:
            raise MobileLinkApiError(f"HTTP error: {e.status}") from e

        content_type = resp.headers.get("Content-Type", "")
        text = None

        # Auth failures often return HTML (login / bot block) or 401/403.
        if resp.status in (401, 403):
            text = await resp.text()
            raise MobileLinkAuthError(f"HTTP {resp.status}: unauthorized/forbidden. Body starts: {text[:120]!r}")

        if "application/json" not in content_type:
            text = await resp.text()
            raise MobileLinkAuthError(
                f"Expected JSON but got {content_type or 'unknown content-type'}. "
                f"Body starts: {text[:120]!r}"
            )

        try:
            data = await resp.json()
        except Exception:
            text = await resp.text()
            raise MobileLinkAuthError(f"Failed to parse JSON. Body starts: {text[:120]!r}")

        if not isinstance(data, list):
            raise MobileLinkApiError(f"Unexpected apparatus list shape: {type(data)}")
        return data

    @staticmethod
    def parse_propane_tanks(apparatus_list: list[dict[str, Any]]) -> list[PropaneTank]:
        tanks: list[PropaneTank] = []
        for a in apparatus_list:
            # type == 2 appears to be propane apparatus (per HAR)
            if a.get("type") != 2:
                continue

            props = {p.get("name"): p.get("value") for p in a.get("properties", []) if isinstance(p, dict)}
            device = props.get("Device") if isinstance(props.get("Device"), dict) else {}

            fuel = props.get("FuelLevel")
            try:
                fuel_f = float(fuel) if fuel is not None else None
            except (TypeError, ValueError):
                fuel_f = None

            tanks.append(
                PropaneTank(
                    apparatus_id=int(a.get("apparatusId")),
                    name=str(a.get("name") or f"Propane Tank {a.get('apparatusId')}"),
                    is_connected=bool(a.get("isConnected", False)),
                    device_id=(device.get("deviceId") if isinstance(device, dict) else None),
                    device_type=(device.get("deviceType") if isinstance(device, dict) else None),
                    battery_level=(device.get("batteryLevel") if isinstance(device, dict) else None),
                    device_status=(device.get("status") if isinstance(device, dict) else None),
                    fuel_level=fuel_f,
                    last_reading=(props.get("LastReading") if isinstance(props.get("LastReading"), str) else None),
                    capacity=(str(props.get("Capacity")) if props.get("Capacity") is not None else None),
                )
            )
        return tanks
