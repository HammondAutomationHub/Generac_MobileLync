from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientResponseError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER_NAME = __name__


class MobileLinkAuthError(Exception):
    """Raised when authentication fails."""


class MobileLinkApiError(Exception):
    """Raised for general API errors."""


@dataclass
class TankDeviceInfo:
    device_id: str | None = None
    device_type: str | None = None
    battery_level: str | None = None
    status: str | None = None


@dataclass
class PropaneTank:
    apparatus_id: int
    name: str
    fuel_level_percent: float | None
    last_reading: str | None
    capacity_gallons: str | None
    is_connected: bool | None
    device: TankDeviceInfo


class MobileLinkApiClient:
    """
    Mobile Link client (cookie-session based), using the same endpoints as the
    web dashboard.

    Auth is handled via the Azure AD B2C "SelfAsserted" step.
    """

    BASE = "https://app.mobilelinkgen.com"
    B2C_HOST = "https://generacconnectivity.b2clogin.com"
    TENANT = "generacconnectivity.onmicrosoft.com"
    POLICY = "B2C_1A_MobileLink_SignIn"

    # App endpoints
    URL_ANTIFORGERY = f"{BASE}/api/v1/Antiforgery/cookie"
    URL_SIGNIN = f"{BASE}/api/Auth/SignIn"
    URL_ACCOUNT_STATUS = f"{BASE}/api/v1/Account/status"
    URL_APPARATUS_LIST = f"{BASE}/api/v2/Apparatus/list"

    # B2C endpoints (known stable pattern)
    def _b2c_authorize_url(self, client_id: str, nonce: str, redirect_uri: str, state: str) -> str:
        # We don't generally need to craft this manually; we follow the redirect from URL_SIGNIN.
        raise NotImplementedError

    def __init__(self, hass: HomeAssistant) -> None:
        self._session = async_get_clientsession(hass)
        self._csrf: str | None = None
        self._tx: str | None = None

    async def login(self, email: str, password: str) -> None:
        """Authenticate and establish a cookie session."""
        try:
            # 1) Ensure antiforgery cookie exists
            await self._session.get(self.URL_ANTIFORGERY)

            # 2) Begin sign-in; this redirects to B2C authorize page
            resp = await self._session.get(self.URL_SIGNIN, params={"email": email})
            if resp.status >= 400:
                raise MobileLinkAuthError(f"Sign-in start failed: HTTP {resp.status}")

            # Follow redirects to get the B2C authorize HTML
            html = await resp.text()

            # Sometimes the first call returns HTML directly (already on B2C). If it's not HTML,
            # follow redirects explicitly.
            if "<!DOCTYPE html" not in html and "<html" not in html.lower():
                resp2 = await self._session.get(resp.url, allow_redirects=True)
                html = await resp2.text()

            # 3) Extract csrf + tx from B2C page HTML
            # Observed patterns:
            #   "csrf":"<token>"
            #   "transId":"StateProperties=...."
            m_csrf = re.search(r'"csrf"\s*:\s*"([^"]+)"', html)
            m_tx = re.search(r'"transId"\s*:\s*"([^"]+)"', html)

            if not m_csrf or not m_tx:
                raise MobileLinkAuthError("Failed to parse B2C login page (csrf/transId not found)")

            csrf_token = m_csrf.group(1)
            tx = m_tx.group(1)

            # 4) POST credentials to SelfAsserted endpoint
            selfasserted = (
                f"{self.B2C_HOST}/{self.TENANT}/{self.POLICY}/SelfAsserted"
            )
            sa_resp = await self._session.post(
                selfasserted,
                params={"tx": tx, "p": self.POLICY},
                data={
                    "request_type": "RESPONSE",
                    "signInName": email,
                    "password": password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            )

            if sa_resp.status >= 400:
                raise MobileLinkAuthError(f"Credential submit failed: HTTP {sa_resp.status}")

            # 5) Confirm step (sets cookies and redirects to app callback)
            confirmed = (
                f"{self.B2C_HOST}/{self.TENANT}/{self.POLICY}/api/CombinedSigninAndSignup/confirmed"
            )
            conf_resp = await self._session.get(
                confirmed,
                params={"rememberMe": "false", "csrf_token": csrf_token, "tx": tx, "p": self.POLICY},
                allow_redirects=True,
            )
            if conf_resp.status >= 400:
                raise MobileLinkAuthError(f"Confirm step failed: HTTP {conf_resp.status}")

            # 6) Verify session
            st = await self._session.get(self.URL_ACCOUNT_STATUS)
            if st.status != 200:
                raise MobileLinkAuthError("Login did not establish an authenticated session")

            self._csrf = csrf_token
            self._tx = tx

        except ClientResponseError as e:
            raise MobileLinkAuthError(str(e)) from e

    async def account_status(self) -> dict[str, Any]:
        resp = await self._session.get(self.URL_ACCOUNT_STATUS)
        if resp.status != 200:
            raise MobileLinkAuthError("Not authenticated")
        return await resp.json()

    async def list_apparatus(self) -> list[dict[str, Any]]:
        resp = await self._session.get(self.URL_APPARATUS_LIST)
        if resp.status == 401:
            raise MobileLinkAuthError("Not authenticated")
        if resp.status != 200:
            text = await resp.text()
            raise MobileLinkApiError(f"Apparatus list failed: HTTP {resp.status} {text[:200]}")
        data = await resp.json()
        if not isinstance(data, list):
            raise MobileLinkApiError("Unexpected apparatus list response shape")
        return data

    @staticmethod
    def _props_dict(apparatus: dict[str, Any]) -> dict[str, Any]:
        props = {}
        for p in apparatus.get("properties", []) or []:
            name = p.get("name")
            if name:
                props[name] = p.get("value")
        return props

    async def discover_propane_tanks(self) -> list[PropaneTank]:
        """Return propane tanks (apparatus type == 2)."""
        apparatus_list = await self.list_apparatus()
        tanks: list[PropaneTank] = []

        for a in apparatus_list:
            if a.get("type") != 2:
                continue

            props = self._props_dict(a)

            device_obj = props.get("Device") or {}
            device = TankDeviceInfo(
                device_id=(device_obj.get("deviceId") if isinstance(device_obj, dict) else None),
                device_type=(device_obj.get("deviceType") if isinstance(device_obj, dict) else None),
                battery_level=(device_obj.get("batteryLevel") if isinstance(device_obj, dict) else None),
                status=(device_obj.get("status") if isinstance(device_obj, dict) else None),
            )

            percent_raw = props.get("FuelLevel")
            try:
                percent = float(percent_raw) if percent_raw is not None else None
            except (TypeError, ValueError):
                percent = None

            tanks.append(
                PropaneTank(
                    apparatus_id=int(a.get("apparatusId")),
                    name=str(a.get("name") or f"Tank {a.get('apparatusId')}"),
                    fuel_level_percent=percent,
                    last_reading=props.get("LastReading"),
                    capacity_gallons=str(props.get("Capacity")) if props.get("Capacity") is not None else None,
                    is_connected=a.get("isConnected"),
                    device=device,
                )
            )

        return tanks
