from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientResponseError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER_NAME = __name__

def _looks_like_bot_block(text: str) -> bool:
    t = (text or "").lower()
    return any(s in t for s in ["incapsula", "captcha", "access denied", "request unsuccessful", "bot"])


def _extract_b2c_error(text: str) -> str | None:
    """Try to extract an Azure AD B2C error code like AADB2C90118 from HTML/JSON-ish text."""
    if not text:
        return None
    m = re.search(r"AADB2C\d{5}", text)
    return m.group(0) if m else None


def _map_b2c_error_to_code(b2c_code: str | None) -> tuple[str, str | None]:
    """Return (our_code, hint)."""
    if not b2c_code:
        return ("unknown", None)
    # Common B2C codes (not exhaustive)
    if b2c_code in ("AADB2C90091",):  # cancelled by user / access denied
        return ("access_denied", None)
    if b2c_code in ("AADB2C90118",):  # password reset
        return ("password_reset_required", "Mobile Link requested a password reset")
    if b2c_code in ("AADB2C90080", "AADB2C90079", "AADB2C90077"):
        return ("account_locked", "Account may be locked or disabled")
    if b2c_code in ("AADB2C90055",):
        return ("invalid_credentials", None)
    # MFA codes vary; treat as MFA required if mentioned
    return ("b2c_error", f"Azure B2C error {b2c_code}")



class MobileLinkAuthError(Exception):
    """Authentication or session establishment failed."""

    def __init__(
        self,
        code: str,
        step: str,
        message: str,
        *,
        status: int | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.step = step
        self.status = status
        self.hint = hint

    def short(self) -> str:
        parts = [self.code, self.step]
        if self.status is not None:
            parts.append(f"HTTP {self.status}")
        return " / ".join(parts)

    def detail(self) -> str:
        msg = str(self)
        if self.hint:
            return f"{msg} ({self.hint})"
        return msg


class MobileLinkApiError(Exception):
    """Non-auth API error."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


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
        """Authenticate and establish a cookie session.

        Raises MobileLinkAuthError with a structured code + step when something goes wrong.
        """
        try:
            # 1) Ensure antiforgery cookie exists (required by the app)
            anti = await self._session.get(self.URL_ANTIFORGERY)
            if anti.status >= 400:
                txt = await anti.text()
                raise MobileLinkAuthError(
                    "antiforgery_failed",
                    "antiforgery",
                    "Failed to obtain antiforgery cookie",
                    status=anti.status,
                    hint=txt[:120] or None,
                )

            # 2) Begin sign-in; this should redirect to the Azure B2C authorize HTML
            resp = await self._session.get(self.URL_SIGNIN, params={"email": email}, allow_redirects=True)
            html = await resp.text()

            if resp.status >= 400:
                if _looks_like_bot_block(html):
                    raise MobileLinkAuthError(
                        "bot_block",
                        "signin_start",
                        "Mobile Link blocked the request (bot protection / captcha)",
                        status=resp.status,
                        hint="Try again later, or login once in the browser from the same network and retry.",
                    )
                b2c = _extract_b2c_error(html)
                code, hint = _map_b2c_error_to_code(b2c)
                raise MobileLinkAuthError(
                    code if code != "unknown" else "signin_start_failed",
                    "signin_start",
                    "Failed to start sign-in flow",
                    status=resp.status,
                    hint=hint or (b2c if b2c else html[:120] or None),
                )

            if _looks_like_bot_block(html):
                raise MobileLinkAuthError(
                    "bot_block",
                    "signin_start",
                    "Mobile Link returned a bot-protection / captcha page",
                    status=resp.status,
                    hint="This integration cannot solve interactive captchas. Try again later.",
                )

            # 3) Parse csrf + transaction id from B2C authorize HTML
            m_csrf = re.search(r'"csrf"\s*:\s*"([^"]+)"', html)
            m_tx = re.search(r'"transId"\s*:\s*"([^"]+)"', html)
            if not m_csrf or not m_tx:
                b2c = _extract_b2c_error(html)
                code, hint = _map_b2c_error_to_code(b2c)
                raise MobileLinkAuthError(
                    code if code != "unknown" else "parse_failed",
                    "parse_b2c",
                    "Could not parse the Azure B2C login page",
                    status=resp.status,
                    hint=hint or (b2c if b2c else "csrf/transId not found"),
                )

            csrf_token = m_csrf.group(1)
            tx = m_tx.group(1)

            # 4) POST credentials to SelfAsserted endpoint
            selfasserted = f"{self.B2C_HOST}/{self.TENANT}/{self.POLICY}/SelfAsserted"
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
            sa_text = await sa_resp.text()

            b2c = _extract_b2c_error(sa_text)
            if sa_resp.status >= 400 or b2c:
                code, hint = _map_b2c_error_to_code(b2c)
                # If no B2C code, assume invalid credentials for 4xx
                if code == "unknown" and sa_resp.status in (400, 401, 403):
                    code = "invalid_credentials"
                raise MobileLinkAuthError(
                    code if code != "unknown" else "credential_submit_failed",
                    "credential_submit",
                    "Authentication was rejected",
                    status=sa_resp.status,
                    hint=hint or (b2c if b2c else sa_text[:160] or None),
                )

            # 5) Confirm step (sets cookies and redirects back to app callback)
            confirmed = f"{self.B2C_HOST}/{self.TENANT}/{self.POLICY}/api/CombinedSigninAndSignup/confirmed"
            conf_resp = await self._session.get(
                confirmed,
                params={"rememberMe": "false", "csrf_token": csrf_token, "tx": tx, "p": self.POLICY},
                allow_redirects=True,
            )
            conf_text = await conf_resp.text()

            if conf_resp.status >= 400:
                if _looks_like_bot_block(conf_text):
                    raise MobileLinkAuthError(
                        "bot_block",
                        "confirm",
                        "Blocked during sign-in confirmation (bot protection)",
                        status=conf_resp.status,
                    )
                b2c = _extract_b2c_error(conf_text)
                code, hint = _map_b2c_error_to_code(b2c)
                raise MobileLinkAuthError(
                    code if code != "unknown" else "confirm_failed",
                    "confirm",
                    "Failed to complete sign-in confirmation",
                    status=conf_resp.status,
                    hint=hint or (b2c if b2c else conf_text[:160] or None),
                )

            # 6) Verify session
            st = await self._session.get(self.URL_ACCOUNT_STATUS)
            st_text = await st.text()

            if st.status != 200:
                if _looks_like_bot_block(st_text):
                    raise MobileLinkAuthError(
                        "bot_block",
                        "account_status",
                        "Blocked while verifying session (bot protection)",
                        status=st.status,
                    )
                raise MobileLinkAuthError(
                    "session_not_established",
                    "account_status",
                    "Login did not establish an authenticated session",
                    status=st.status,
                    hint=st_text[:160] or None,
                )

            self._csrf = csrf_token
            self._tx = tx

        except ClientResponseError as e:
            raise MobileLinkAuthError(
                "http_error",
                "aiohttp",
                str(e),
                status=getattr(e, "status", None),
            ) from e

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
