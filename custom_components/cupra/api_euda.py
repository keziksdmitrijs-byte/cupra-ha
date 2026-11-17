"""Client for the VW Group EU Data Act portal (OIDC login + data delivery).

The login flow (Auth0 Universal Login for CUPRA, classic VW identity fallback,
marketing/terms interstitials) is adapted from HA_VAG-EU-Data-Act
(MIT License, (c) 2026 Jernej Fijačko). See THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import io
import json
import logging
import re
import uuid
import zipfile
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import aiohttp

from .const import (
    DEFAULT_COUNTRY,
    DEFAULT_LANGUAGE,
    EUDA_BASE_URL,
    EUDA_HOSTS,
    EUDA_CALLBACK_PATH,
    EUDA_CLIENT_ID,
    EUDA_DOWNLOAD_PATH,
    EUDA_LIST_PATH,
    EUDA_METADATA_PATH,
    EUDA_NO_CONTENT_SUFFIX,
    EUDA_REDIRECT_URI,
    EUDA_REQUEST_TYPES,
    EUDA_RELATION_PATH,
    EUDA_SCOPE,
    EUDA_VEHICLES_PATH,
    IDENTITY_BASE,
    OIDC_AUTHORIZE_URL,
    TRANSIENT_STATUSES,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)
_MAX_REDIRECTS = 12


class CupraApiError(Exception):
    """API failure; ``status`` is the HTTP status when there is one."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class CupraAuthError(CupraApiError):
    """Credentials rejected or session cannot be established."""


def _login_failure(message: str, status: int | None = None) -> None:
    if status in TRANSIENT_STATUSES:
        raise CupraApiError(message, status=status)
    raise CupraAuthError(message, status=status)


# ---------------------------------------------------------------------------
# HTML helpers (shared with api_ola)
# ---------------------------------------------------------------------------


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.fields: dict[str, str] = {}
        self._in_form = False
        self._done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done:
            return
        a = dict(attrs)
        if tag == "form" and self.action is None:
            self.action = a.get("action")
            self._in_form = True
        elif tag == "input" and self._in_form and a.get("name"):
            self.fields[a["name"]] = a.get("value") or ""
        elif tag == "button" and self._in_form and a.get("name"):
            if (a.get("type") or "submit") == "submit":
                self.fields[a["name"]] = a.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._in_form:
            self._in_form = False
            self._done = True


def _template_model(html: str) -> dict:
    idx = html.find("templateModel")
    if idx == -1:
        return {}
    start = html.find("{", idx)
    depth = 0
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except ValueError:
                    return {}
    return {}


def login_fields(html: str) -> tuple[dict[str, str], str | None]:
    """Hidden form fields + JS templateModel values (hmac, relayState, csrf)."""
    form = _FormParser()
    form.feed(html)
    fields = dict(form.fields)
    model = _template_model(html)
    for key in ("hmac", "relayState"):
        if model.get(key):
            fields[key] = model[key]
    m = re.search(r"csrf_token\s*[:=]\s*['\"]([^'\"]+)['\"]", html)
    if m:
        fields.setdefault("_csrf", m.group(1))
    return fields, form.action


def login_error(html: str) -> str | None:
    model = _template_model(html)
    err = model.get("error") or model.get("errorCode")
    if isinstance(err, dict):
        return err.get("text") or err.get("errorCode") or str(err)
    if err:
        return str(err)
    m = re.search(r'data-error-code=["\']([^"\']+)["\']', html)
    if m:
        code = m.group(1)
        if code in {"wrong-email-or-password", "wrong-email-credentials"}:
            return "Wrong e-mail or password"
        return code.replace("-", " ")
    return None


def is_auth0(url: str, fields: dict[str, str]) -> bool:
    if "/u/login" in urlparse(url).path:
        return True
    return "username" in fields and "state" in fields and "hmac" not in fields


def browser_headers(country: str, language: str, referer: str | None = None, ua: str = USER_AGENT) -> dict[str, str]:
    h = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": f"{language}-{country.upper()},{language};q=0.9,en;q=0.8",
    }
    if referer:
        h["Referer"] = referer
        p = urlparse(referer)
        h["Origin"] = f"{p.scheme}://{p.netloc}"
    return h


def marketing_skip(url: str) -> tuple[str, str, dict[str, str] | None] | None:
    """Return (method, url, form) to skip an optional marketing-consent page."""
    p = urlparse(url)
    if "/consent/marketing/" in p.path:
        cb = parse_qs(p.query).get("callback", [""])[0]
        if not cb:
            raise CupraAuthError("Marketing consent page without continuation")
        target = urlparse(urljoin(url, cb))
        if target.netloc not in EUDA_HOSTS | {urlparse(IDENTITY_BASE).netloc}:
            raise CupraAuthError("Unexpected marketing consent continuation host")
        return "GET", urlunparse(target), None
    path = p.path.rstrip("/")
    if "/login/ui/marketing-consent" in path and not path.endswith(("/skip", "/accept")):
        qs = parse_qs(p.query)
        relay, state = qs.get("relayState", [""])[0], qs.get("state", [""])[0]
        if not relay or not state:
            raise CupraAuthError("Marketing consent page without relayState/state")
        skip = urlunparse(p._replace(path=f"{path}/skip", query="", fragment=""))
        return "POST", skip, {"relayState": relay, "state": state}
    return None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class EudaClient:
    """Authenticated session against the EU Data Act portal."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        *,
        country: str = DEFAULT_COUNTRY,
        language: str = DEFAULT_LANGUAGE,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._country = (country or DEFAULT_COUNTRY).lower()
        self._language = (language or DEFAULT_LANGUAGE).lower()
        self._logged_in = False
        # identifier -> request type ("partial" / "all")
        self.request_types: dict[str, str] = {}

    # -- login ---------------------------------------------------------------

    def _h(self, referer: str | None = None) -> dict[str, str]:
        return browser_headers(self._country, self._language, referer)

    def authorize_url(self) -> str:
        params = {
            "client_id": EUDA_CLIENT_ID,
            "response_type": "code",
            "scope": EUDA_SCOPE,
            "state": f"{self._country}__{self._language}__CUPRA",
            "redirect_uri": EUDA_REDIRECT_URI,
            "prompt": "login",
        }
        return f"{OIDC_AUTHORIZE_URL}?{urlencode(params)}"

    @staticmethod
    def _is_callback(url: str) -> bool:
        p = urlparse(url)
        return p.netloc in EUDA_HOSTS and p.path.startswith(EUDA_CALLBACK_PATH)

    async def _follow(self, resp: aiohttp.ClientResponse) -> aiohttp.ClientResponse:
        for _ in range(_MAX_REDIRECTS):
            if self._is_callback(str(resp.url)) or resp.status not in (301, 302, 303):
                return resp
            loc = resp.headers.get("Location")
            if not loc:
                return resp
            nxt = urljoin(str(resp.url), loc)
            ref = str(resp.url)
            resp.release()
            resp = await self._session.get(nxt, headers=self._h(ref), allow_redirects=False)
        resp.release()
        raise CupraApiError("Too many login redirects")

    async def _post_form(self, url: str, data: dict[str, str], referer: str) -> aiohttp.ClientResponse:
        resp = await self._session.post(url, data=data, headers=self._h(referer), allow_redirects=False)
        return await self._follow(resp)

    async def async_login(self) -> None:
        try:
            await self._login()
        except aiohttp.ClientError as err:
            raise CupraApiError(f"Network error during login: {err}") from err
        self._logged_in = True

    async def _login(self) -> None:
        async with self._session.get(self.authorize_url(), headers=self._h(f"{EUDA_BASE_URL}/")) as resp:
            url, html, status = str(resp.url), await resp.text(), resp.status
        fields, action = login_fields(html)
        if is_auth0(url, fields):
            if "state" not in fields:
                _login_failure(f"Unexpected sign-in form ({sorted(fields)})", status)
            fields.update(username=self._email, password=self._password)
            fields.setdefault("action", "default")
            resp = await self._post_form(url, fields, url)
        else:
            if "hmac" not in fields or "_csrf" not in fields:
                _login_failure(f"Unexpected sign-in form ({sorted(fields)})", status)
            fields["email"] = self._email
            async with self._session.post(urljoin(url, action or ""), data=fields, headers=self._h(url)) as r2:
                auth_url, auth_html, auth_status = str(r2.url), await r2.text(), r2.status
            f2, a2 = login_fields(auth_html)
            if "hmac" not in f2 or "_csrf" not in f2:
                _login_failure(login_error(auth_html) or "Password form not returned – check e-mail", auth_status)
            f2.update(email=self._email, password=self._password)
            target = urljoin(auth_url, a2) if a2 else auth_url.split("?", 1)[0]
            resp = await self._post_form(target, f2, auth_url)
        async with resp:
            await self._finish(resp)

    async def _finish(self, resp: aiohttp.ClientResponse, depth: int = 0) -> None:
        if depth > 3:
            raise CupraAuthError("Login stuck on interstitial pages")
        landing = str(resp.url)
        if self._is_callback(landing):
            tok = resp.cookies.get("access_token")
            if not getattr(tok, "value", tok):
                raise CupraAuthError("Portal did not set a session (access_token cookie missing)")
            return
        skip = marketing_skip(landing)
        if skip:
            method, url, form = skip
            if method == "GET":
                nxt = await self._follow(await self._session.get(url, headers=self._h(landing), allow_redirects=False))
            else:
                nxt = await self._post_form(url, form or {}, landing)
            async with nxt:
                await self._finish(nxt, depth + 1)
            return
        html = await resp.text()
        if resp.status >= 400:
            _login_failure(login_error(html) or f"Login rejected (HTTP {resp.status})", resp.status)
        if "terms-and-conditions" in landing:
            fields, action = login_fields(html)
            if not {"_csrf", "relayState", "hmac"} <= set(fields):
                raise CupraAuthError("Updated terms and conditions must be accepted on cupraofficial / My Cupra first")
            target = urljoin(landing, action) if action else landing.split("?", 1)[0]
            nxt = await self._post_form(target, fields, landing)
            async with nxt:
                await self._finish(nxt, depth + 1)
            return
        raise CupraAuthError(login_error(html) or f"Login did not complete (ended at {urlparse(landing).path})")

    # -- data ----------------------------------------------------------------

    async def _request(self, path: str, headers: dict[str, str] | None = None, *, raw: bool = False) -> tuple[int, Any]:
        if not self._logged_in:
            await self.async_login()
        url = f"{EUDA_BASE_URL}{path}"
        h = {"User-Agent": USER_AGENT, **(headers or {})}
        for attempt in (0, 1):
            try:
                async with self._session.get(url, headers=h) as resp:
                    if resp.status in (401, 403) and attempt == 0:
                        self._logged_in = False
                        await self.async_login()
                        continue
                    body = await (resp.read() if raw else resp.text())
                    return resp.status, body
            except aiohttp.ClientError as err:
                raise CupraApiError(f"Connection error: {err}") from err
        raise CupraAuthError("Session rejected after re-login")

    async def _json(self, path: str, headers: dict[str, str] | None = None) -> Any:
        status, text = await self._request(path, headers)
        if status >= 400:
            raise CupraApiError(f"GET {path.split('?')[0]} -> HTTP {status}", status=status)
        try:
            return json.loads(text)
        except ValueError as err:
            raise CupraApiError(f"Invalid JSON from {path}") from err

    async def async_list_vehicles(self) -> list[dict[str, str]]:
        payload = await self._json(EUDA_VEHICLES_PATH)
        found: dict[str, dict[str, str]] = {}

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                vin = node.get("vin") or node.get("vehicleIdentificationNumber")
                if isinstance(vin, str) and len(vin) == 17:
                    entry = found.setdefault(vin, {"vin": vin})
                    for k in ("vehicleNickname", "nickname", "modelName", "model"):
                        if node.get(k) and isinstance(node[k], str):
                            entry.setdefault("nickname" if "ick" in k else "model", node[k])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(payload)
        for veh in found.values():
            try:
                rel = await self._json(EUDA_RELATION_PATH.format(vin=veh["vin"]), {"traceid": f"vehicle-relation-fetch-{uuid.uuid4()}"})
                rel = rel.get("relation") or {}
                if rel.get("vehicleNickname"):
                    veh["nickname"] = rel["vehicleNickname"]
            except CupraApiError as err:
                _LOGGER.debug("No relation for %s: %s", veh["vin"][-4:], err)
        return list(found.values())

    async def async_get_identifier(self, vin: str) -> str | None:
        """Return the data request ``Identifier`` (None = no request on the portal).

        A customised (continuous, ``partial``) request is preferred; a one-off
        "Get your data" request (``all``) is used as a fallback.
        """
        for req_type in EUDA_REQUEST_TYPES:
            try:
                meta = await self._json(EUDA_METADATA_PATH.format(vin=vin, type=req_type))
            except CupraApiError as err:
                if err.status in (400, 404):
                    continue
                raise
            ident = find_identifier(meta)
            if ident:
                self.request_types[ident] = req_type
                return ident
        return None

    def request_type(self, identifier: str) -> str | None:
        return self.request_types.get(identifier)

    def _types_for(self, identifier: str) -> tuple[str, ...]:
        known = self.request_types.get(identifier)
        return (known,) if known else EUDA_REQUEST_TYPES

    async def async_list_datasets(self, vin: str, identifier: str) -> list[dict]:
        for req_type in self._types_for(identifier):
            status, text = await self._request(EUDA_LIST_PATH.format(vin=vin, identifier=identifier), {"type": req_type})
            if status in (400, 404):
                continue
            if status >= 400:
                raise CupraApiError(f"Dataset list -> HTTP {status}", status=status)
            try:
                data = json.loads(text)
            except ValueError as err:
                raise CupraApiError("Invalid dataset list") from err
            self.request_types[identifier] = req_type
            files = data if isinstance(data, list) else data.get("files", [])
            return [f for f in files if isinstance(f, dict) and f.get("name")]
        return []

    async def async_download(self, vin: str, identifier: str, name: str) -> dict:
        if name.endswith(EUDA_NO_CONTENT_SUFFIX):
            raise CupraApiError(f"{name} has no content")
        req_type = self.request_types.get(identifier, EUDA_REQUEST_TYPES[0])
        status, body = await self._request(
            EUDA_DOWNLOAD_PATH.format(vin=vin, identifier=identifier),
            {"filename": name, "type": req_type},
            raw=True,
        )
        if status >= 400:
            raise CupraApiError(f"Download -> HTTP {status}", status=status)
        return parse_zip(body, name)


def find_identifier(meta: Any) -> str | None:
    """The metadata body shape is undocumented; find the first Identifier-like value."""
    if isinstance(meta, dict):
        for k, v in meta.items():
            if k.lower() in ("identifier", "requestidentifier", "datarequestidentifier") and isinstance(v, (str, int)) and str(v):
                return str(v)
        for v in meta.values():
            found = find_identifier(v)
            if found:
                return found
    elif isinstance(meta, list):
        for v in meta:
            found = find_identifier(v)
            if found:
                return found
    return None


def parse_zip(raw: bytes, name: str = "dataset") -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            members = [n for n in zf.namelist() if n.lower().endswith(".json")]
            if not members:
                raise CupraApiError(f"No JSON inside {name}")
            with zf.open(members[0]) as fh:
                return json.loads(fh.read().decode("utf-8"))
    except (zipfile.BadZipFile, ValueError) as err:
        raise CupraApiError(f"Could not read {name}: {err}") from err


def newest_dataset(files: list[dict]) -> dict | None:
    """Newest ZIP that actually carries data."""
    real = [f for f in files if not str(f.get("name", "")).endswith(EUDA_NO_CONTENT_SUFFIX)]
    if not real:
        return None
    return max(real, key=lambda f: (str(f.get("createdOn") or ""), str(f.get("name"))))
