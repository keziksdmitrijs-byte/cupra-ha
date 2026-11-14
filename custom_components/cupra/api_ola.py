"""Client for the My Cupra app backend (OLA): live status, GPS and remote commands.

Endpoints, headers and the PKCE login were learned from pycupra
(Apache-2.0, https://github.com/WulfgarW/pycupra). See THIRD_PARTY_NOTICES.md.

Since 8 June 2026 VW requires a Firebase App Check token on most OLA
endpoints. Without it the backend answers HTTP 403; we surface that as
``OlaBlockedError`` so the integration can switch commands off cleanly
instead of failing the whole entry.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import secrets
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import aiohttp

from .api_euda import (
    CupraApiError,
    CupraAuthError,
    browser_headers,
    is_auth0,
    login_error,
    login_fields,
    marketing_skip,
)
from .const import (
    OIDC_AUTHORIZE_URL,
    OLA_APP_VERSION,
    OLA_BASE,
    OLA_CLIENT_ID,
    OLA_REDIRECT_URI,
    OLA_SCOPE,
    OLA_TOKEN_URL,
    OLA_USER_AGENT,
    OLA_USERINFO_URL,
)

_LOGGER = logging.getLogger(__name__)


class OlaBlockedError(CupraApiError):
    """Backend refused the request (HTTP 403) – App Check token missing/expired."""


class OlaThrottledError(CupraApiError):
    """Action rate limit reached (HTTP 429)."""


def _pkce() -> tuple[str, str]:
    verifier = re.sub(r"[^a-zA-Z0-9]+", "", base64.urlsafe_b64encode(os.urandom(40)).decode())
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


class OlaClient:
    """Minimal async My Cupra client (only what the integration uses)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        *,
        spin: str | None = None,
        appcheck_token: str | None = None,
        tokens: dict[str, Any] | None = None,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._spin = spin or None
        self._appcheck = (appcheck_token or "").strip() or None
        self.tokens: dict[str, Any] = dict(tokens or {})
        self.user_id: str | None = self.tokens.get("user_id")

    # -- auth ----------------------------------------------------------------

    @property
    def _auth_h(self) -> dict[str, str]:
        h = browser_headers("de", "en", ua=OLA_USER_AGENT)
        h["x-requested-with"] = "com.cupra.mycupra"
        return h

    def _api_h(self) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": OLA_USER_AGENT,
            "app-version": OLA_APP_VERSION,
            "app-brand": "cupra",
            "app-market": "android",
            "origin": "app",
            "Accept-Language": "en_GB",
        }
        if self.tokens.get("access_token"):
            h["Authorization"] = f"Bearer {self.tokens['access_token']}"
        if self.user_id:
            h["User-ID"] = self.user_id
        if self._appcheck:
            h["X-Firebase-AppCheck"] = self._appcheck
        return h

    async def async_login(self) -> None:
        try:
            await self._login()
        except aiohttp.ClientError as err:
            raise CupraApiError(f"Network error during My Cupra login: {err}") from err

    async def _login(self) -> None:
        verifier, challenge = _pkce()
        params = {
            "client_id": OLA_CLIENT_ID,
            "response_type": "code",
            "scope": OLA_SCOPE,
            "redirect_uri": OLA_REDIRECT_URI,
            "state": secrets.token_urlsafe(16),
            "nonce": secrets.token_urlsafe(16),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        location = await self._walk(f"{OIDC_AUTHORIZE_URL}?{urlencode(params)}")
        if location is None or not location.startswith(OLA_REDIRECT_URI):
            raise CupraAuthError("My Cupra login did not return an authorization code")
        qs = parse_qs(urlparse(location).query)
        if qs.get("user_id"):
            self.user_id = qs["user_id"][0]
        code = qs.get("code", [""])[0]
        if not code:
            raise CupraAuthError("My Cupra login: no code in callback")
        data = {
            "redirect_uri": OLA_REDIRECT_URI,
            "client_id": OLA_CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
        }
        await self._token_request(data)
        await self._load_user_id()

    async def _walk(self, url: str) -> str | None:
        """Drive the identity pages until the cupra:// redirect; return that URL."""
        referer: str | None = None
        for _ in range(15):
            async with self._session.get(url, headers={**self._auth_h, **({"Referer": referer} if referer else {})}, allow_redirects=False) as resp:
                loc = resp.headers.get("Location")
                if loc:
                    if loc.startswith(OLA_REDIRECT_URI):
                        return loc
                    referer, url = url, urljoin(url, loc)
                    self._check_location(url)
                    continue
                html = await resp.text()
                if resp.status >= 400:
                    raise CupraAuthError(login_error(html) or f"My Cupra login HTTP {resp.status}", status=resp.status)
                page = str(resp.url)
            skip = marketing_skip(page)
            if skip and skip[0] == "GET":
                referer, url = page, skip[1]
                continue
            fields, action = login_fields(html)
            if is_auth0(page, fields):
                fields.update(username=self._email, password=self._password)
                fields.setdefault("action", "default")
                post_url = page
            elif "hmac" in fields and "_csrf" in fields:
                fields.update(email=self._email, password=self._password)
                post_url = urljoin(page, action or page)
            elif skip:
                fields, post_url = skip[2] or {}, skip[1]
            else:
                raise CupraAuthError(login_error(html) or "Unexpected My Cupra login page")
            async with self._session.post(post_url, data=fields, headers={**self._auth_h, "Referer": page}, allow_redirects=False) as resp:
                loc = resp.headers.get("Location")
                if not loc:
                    raise CupraAuthError(login_error(await resp.text()) or "My Cupra rejected the credentials")
                if loc.startswith(OLA_REDIRECT_URI):
                    return loc
                referer, url = post_url, urljoin(post_url, loc)
                self._check_location(url)
        raise CupraAuthError("My Cupra login: too many redirects")

    @staticmethod
    def _check_location(url: str) -> None:
        q = parse_qs(urlparse(url).query)
        err = (q.get("error") or [""])[0]
        if err:
            if "password" in err or "credentials" in err:
                raise CupraAuthError("Wrong e-mail or password")
            if "throttled" in err:
                raise CupraApiError("Account temporarily locked by VW (too many logins)", status=429)
            raise CupraAuthError(f"My Cupra login error: {err}")
        if "terms-and-conditions" in url or ("/consent" in url and "marketing" not in url):
            raise CupraAuthError("Open the My Cupra app and accept the terms/consents first")

    async def _token_request(self, data: dict[str, str]) -> None:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": OLA_USER_AGENT,
            "app-version": OLA_APP_VERSION,
            "app-brand": "cupra",
            "app-market": "android",
            "X-Platform": "Android",
        }
        if self.user_id:
            h["User-ID"] = self.user_id
        async with self._session.post(OLA_TOKEN_URL, data=data, headers=h) as resp:
            try:
                body = await resp.json(content_type=None)
            except ValueError:
                body = {}
            if resp.status == 403:
                raise OlaBlockedError("My Cupra token endpoint returned 403", status=403)
            if resp.status >= 400 or "access_token" not in (body or {}):
                err = (body or {}).get("error_description") or (body or {}).get("error") or f"HTTP {resp.status}"
                raise CupraAuthError(f"My Cupra token request failed: {err}", status=resp.status)
        self.tokens.update({k: v for k, v in body.items() if k.endswith("_token") or k == "expires_in"})
        self.tokens["expires_at"] = time.time() + int(body.get("expires_in", 3600)) - 60
        if body.get("appcheck_token") and not self._appcheck:
            self._appcheck = body["appcheck_token"]

    async def _load_user_id(self) -> None:
        if self.user_id:
            self.tokens["user_id"] = self.user_id
            return
        try:
            async with self._session.get(OLA_USERINFO_URL, headers=self._api_h()) as resp:
                if resp.status == 200:
                    info = await resp.json(content_type=None)
                    self.user_id = info.get("brandid") or info.get("sub")
        except (aiohttp.ClientError, ValueError):
            pass
        if self.user_id:
            self.tokens["user_id"] = self.user_id

    async def async_ensure_token(self) -> None:
        if self.tokens.get("access_token") and time.time() < float(self.tokens.get("expires_at", 0)):
            return
        if self.tokens.get("refresh_token"):
            try:
                await self._token_request(
                    {
                        "grant_type": "refresh_token",
                        "client_id": OLA_CLIENT_ID,
                        "refresh_token": self.tokens["refresh_token"],
                    }
                )
                return
            except CupraAuthError:
                _LOGGER.debug("My Cupra refresh failed, doing a full login")
        await self.async_login()

    # -- requests ------------------------------------------------------------

    async def _call(self, method: str, path: str, json: Any = None, extra: dict[str, str] | None = None) -> Any:
        await self.async_ensure_token()
        url = path if path.startswith("http") else f"{OLA_BASE}{path}"
        for attempt in (0, 1):
            try:
                async with self._session.request(method, url, json=json, headers={**self._api_h(), **(extra or {})}) as resp:
                    if resp.status == 401 and attempt == 0:
                        self.tokens.pop("access_token", None)
                        self.tokens["expires_at"] = 0
                        await self.async_ensure_token()
                        continue
                    if resp.status == 403:
                        raise OlaBlockedError(f"{method} {urlparse(url).path} -> 403", status=403)
                    if resp.status == 429:
                        raise OlaThrottledError("Too many remote actions – start the car to reset the limit", status=429)
                    if resp.status == 204:
                        return {"_status": 204}
                    if resp.status >= 400:
                        raise CupraApiError(f"{method} {urlparse(url).path} -> HTTP {resp.status}", status=resp.status)
                    text = await resp.text()
                    if not text:
                        return {}
                    try:
                        return await resp.json(content_type=None)
                    except ValueError:
                        return {}
            except aiohttp.ClientError as err:
                raise CupraApiError(f"Connection error: {err}") from err
        raise CupraAuthError("My Cupra session rejected")

    async def async_get_vehicles(self) -> list[dict]:
        data = await self._call("GET", f"/v2/users/{self.user_id}/garage/vehicles")
        return data.get("vehicles", []) if isinstance(data, dict) else []

    async def async_fetch_all(self, vin: str) -> dict[str, Any]:
        """Fetch every read endpoint we map. Raises OlaBlockedError if all are refused."""
        out: dict[str, Any] = {}
        calls = {
            "mycar": f"/v5/users/{self.user_id}/vehicles/{vin}/mycar",
            "status": f"/v2/vehicles/{vin}/status",
            "mileage": f"/v1/vehicles/{vin}/mileage",
            "ranges": f"/v1/vehicles/{vin}/ranges",
            "position": f"/v1/vehicles/{vin}/parkingposition",
            "climater_status": f"/v1/vehicles/{vin}/climatisation/status",
            "climater_settings": f"/v2/vehicles/{vin}/climatisation/settings",
            "charging_status": f"/v1/vehicles/{vin}/charging/status",
            "charging_info": f"/v1/vehicles/{vin}/charging/info",
        }
        blocked = 0
        for name, path in calls.items():
            try:
                out[name] = await self._call("GET", path)
            except OlaBlockedError:
                blocked += 1
            except CupraApiError as err:
                _LOGGER.debug("OLA %s unavailable: %s", name, err)
        if blocked and blocked >= len(calls) - 1:
            raise OlaBlockedError("My Cupra API refused access (App Check)", status=403)
        result: dict[str, Any] = {
            "mycar": out.get("mycar") or {},
            "status": out.get("status") or {},
            "mileage": out.get("mileage") or {},
            "ranges": (out.get("ranges") or {}).get("ranges", []) if isinstance(out.get("ranges"), dict) else [],
            "climater": {"status": out.get("climater_status") or {}, "settings": out.get("climater_settings") or {}},
            "charging": {"status": out.get("charging_status") or {}, "info": out.get("charging_info") or {}},
        }
        pos = out.get("position") or {}
        if pos.get("_status") == 204:
            result["moving"] = True
        elif "lat" in pos:
            result["position"] = pos
        return result

    # -- commands ------------------------------------------------------------

    async def _sec_token(self) -> dict[str, str]:
        if not self._spin:
            raise CupraApiError("S-PIN is required for this action – add it in the integration options")
        data = await self._call("POST", f"/v2/users/{self.user_id}/spin/verify", json={"spin": self._spin})
        token = (data or {}).get("securityToken")
        if not token:
            raise CupraApiError("S-PIN was not accepted")
        return {"SecToken": token}

    async def async_lock(self, vin: str, lock: bool) -> Any:
        extra = await self._sec_token()
        return await self._call("POST", f"/v1/vehicles/{vin}/access/{'lock' if lock else 'unlock'}", extra=extra)

    async def async_climate(self, vin: str, on: bool, temp: float | None = None) -> Any:
        if on:
            body = {"targetTemperature": float(temp or 21.0), "targetTemperatureUnit": "celsius"}
            return await self._call("POST", f"/v2/vehicles/{vin}/climatisation/start", json=body)
        return await self._call("POST", f"/vehicles/{vin}/climatisation/requests/stop")

    async def async_charging(self, vin: str, on: bool) -> Any:
        return await self._call("POST", f"/vehicles/{vin}/charging/requests/{'start' if on else 'stop'}")

    async def async_window_heating(self, vin: str, on: bool) -> Any:
        return await self._call("POST", f"/vehicles/{vin}/windowheating/requests/{'start' if on else 'stop'}")

    async def async_honk_flash(self, vin: str, lat: float, lon: float, honk: bool) -> Any:
        body = {
            "mode": "honkandflash" if honk else "flash",
            "userPosition": {"latitude": int(lat * 10000) / 10000, "longitude": int(lon * 10000) / 10000},
        }
        return await self._call("POST", f"/v1/vehicles/{vin}/honk-and-flash", json=body)

    async def async_wakeup(self, vin: str) -> Any:
        return await self._call("POST", f"/v1/vehicles/{vin}/vehicle-wakeup/request")
