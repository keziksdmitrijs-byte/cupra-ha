"""Update coordinator: EU Data Act snapshots + optional live My Cupra data."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import parser
from .api_euda import CupraApiError, CupraAuthError, EudaClient, newest_dataset
from .api_ola import OlaBlockedError, OlaClient, OlaThrottledError
from .const import (
    CONF_APPCHECK,
    CONF_COUNTRY,
    CONF_IDENTIFIER,
    CONF_LANGUAGE,
    CONF_MODEL,
    CONF_NICKNAME,
    CONF_OLA_INTERVAL,
    CONF_POWERTRAIN,
    CONF_SPIN,
    CONF_USE_OLA,
    CONF_VIN,
    DEFAULT_COUNTRY,
    DEFAULT_LANGUAGE,
    DEFAULT_OLA_INTERVAL,
    DOMAIN,
    MODEL_AUTO,
    MODELS,
    STALE_AFTER,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
_STORE_VERSION = 1
_OLA_BLOCKED_RETRY = timedelta(hours=6)


def _now() -> datetime:
    return datetime.now(UTC)


def guess_model(*names: str | None) -> str | None:
    text = " ".join(n for n in names if n).lower()
    if not text:
        return None
    if "sportstourer" in text or "leon st" in text or "leon sp" in text:
        return "leon_st"
    for key in ("terramar", "tavascan", "formentor", "born", "raval", "ateca", "leon"):
        if key in text:
            return key
    return None


class CupraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """One coordinator per vehicle (config entry)."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{entry.data[CONF_VIN][-6:]}", update_interval=UPDATE_INTERVAL, config_entry=entry)
        self.vin: str = entry.data[CONF_VIN]
        self.identifier: str | None = entry.data.get(CONF_IDENTIFIER)
        self._session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
        opts = {**entry.data, **entry.options}
        self.euda = EudaClient(
            self._session,
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
            country=opts.get(CONF_COUNTRY, DEFAULT_COUNTRY),
            language=opts.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
        )
        self.use_ola: bool = bool(opts.get(CONF_USE_OLA, True))
        self.ola: OlaClient | None = None
        if self.use_ola:
            self.ola = OlaClient(
                self._session,
                entry.data[CONF_EMAIL],
                entry.data[CONF_PASSWORD],
                spin=opts.get(CONF_SPIN),
                appcheck_token=opts.get(CONF_APPCHECK),
            )
        self.ola_interval = timedelta(minutes=int(opts.get(CONF_OLA_INTERVAL, DEFAULT_OLA_INTERVAL)))
        self.model_option: str = opts.get(CONF_MODEL, MODEL_AUTO)
        self.powertrain_option: str = opts.get(CONF_POWERTRAIN, "auto")
        self.nickname: str | None = entry.data.get(CONF_NICKNAME)

        self._store: Store = Store(hass, _STORE_VERSION, f"{DOMAIN}.{self.vin}")
        self.fields: dict[str, parser.FieldValue] = {}
        self.last_dataset: str | None = None
        self.captured_at: datetime | None = None
        self.euda_status = "starting"
        self.euda_error: str | None = None
        self.ola_raw: dict[str, Any] = {}
        self.ola_status = "disabled" if not self.use_ola else "starting"
        self.ola_error: str | None = None
        self.ola_updated: datetime | None = None
        self._ola_next: datetime = _now()
        self.last_command: dict[str, Any] | None = None

    # -- persistence -------------------------------------------------------------

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        for name, (value, ts) in (stored.get("fields") or {}).items():
            self.fields[name] = parser.FieldValue(value, parser.parse_timestamp(ts))
        self.last_dataset = stored.get("last_dataset")
        self.identifier = self.identifier or stored.get("identifier")
        self.captured_at = parser.parse_timestamp(stored.get("captured_at"))
        if stored.get("ola"):
            self.ola_raw = stored["ola"]
        if self.ola and stored.get("ola_tokens"):
            self.ola.tokens = stored["ola_tokens"]
            self.ola.user_id = stored["ola_tokens"].get("user_id")

    def _save(self) -> None:
        def data() -> dict:
            return {
                "fields": {k: [v.value, v.captured_at.isoformat() if v.captured_at else None] for k, v in self.fields.items()},
                "last_dataset": self.last_dataset,
                "identifier": self.identifier,
                "captured_at": self.captured_at.isoformat() if self.captured_at else None,
                "ola": self.ola_raw,
                "ola_tokens": self.ola.tokens if self.ola else None,
            }

        self._store.async_delay_save(data, 10)

    # -- polling -------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        await self._update_euda()
        if self.ola and _now() >= self._ola_next:
            await self._update_ola()
        if self.euda_status == "auth_failed" and self.ola_status != "ok":
            raise ConfigEntryAuthFailed("Cupra ID rejected the credentials")
        if not self.fields and not self.ola_raw and self.euda_status == "error":
            raise UpdateFailed(self.euda_error or "No data")
        return self._build()

    async def _update_euda(self) -> None:
        try:
            # A one-off "Get your data" request is only a fallback: keep looking
            # for a customised (continuous) request and switch to it once it exists.
            if not self.identifier or self.euda.request_type(self.identifier) != "partial":
                found = await self.euda.async_get_identifier(self.vin)
                if found != self.identifier:  # None = the one-off request expired
                    self.identifier = found
                    self._save()
            if not self.identifier:
                self.euda_status = "no_subscription"
                self._issue("no_subscription", True)
                return
            self._issue("no_subscription", self.euda.request_type(self.identifier) == "all")
            files = await self.euda.async_list_datasets(self.vin, self.identifier)
            if not files:
                fresh = await self.euda.async_get_identifier(self.vin)
                if fresh and fresh != self.identifier:
                    self.identifier = fresh
                    self._save()
                    files = await self.euda.async_list_datasets(self.vin, fresh)
            newest = newest_dataset(files)
            if newest is None:
                self.euda_status = "waiting_for_data"
                return
            if newest["name"] != self.last_dataset:
                payload = await self.euda.async_download(self.vin, self.identifier, newest["name"])
                new_fields, captured = parser.parse_dataset(payload)
                self.fields = parser.merge_fields(self.fields, new_fields)
                self.last_dataset = newest["name"]
                if captured and (self.captured_at is None or captured > self.captured_at):
                    self.captured_at = captured
                self._save()
            self.euda_status = "ok"
            self.euda_error = None
        except CupraAuthError as err:
            self.euda_status = "auth_failed"
            self.euda_error = str(err)
            _LOGGER.warning("EU Data Act login failed: %s", err)
        except CupraApiError as err:
            self.euda_status = "error"
            self.euda_error = str(err)
            _LOGGER.debug("EU Data Act update failed: %s", err)

    async def _update_ola(self) -> None:
        assert self.ola is not None
        try:
            raw = await self.ola.async_fetch_all(self.vin)
            self.ola_raw = raw
            self.ola_updated = _now()
            self.ola_status = "ok"
            self.ola_error = None
            self._ola_next = _now() + self.ola_interval
            self._issue("ola_blocked", False)
            self._save()
        except OlaBlockedError as err:
            self.ola_status = "blocked"
            self.ola_error = str(err)
            self._ola_next = _now() + _OLA_BLOCKED_RETRY
            self._issue("ola_blocked", True)
            _LOGGER.info("My Cupra API is blocked (App Check); live data and commands are off. Retrying in 6 h")
        except CupraAuthError as err:
            self.ola_status = "auth_failed"
            self.ola_error = str(err)
            self._ola_next = _now() + _OLA_BLOCKED_RETRY
        except CupraApiError as err:
            self.ola_status = "error"
            self.ola_error = str(err)
            self._ola_next = _now() + self.ola_interval

    def _issue(self, key: str, active: bool) -> None:
        issue_id = f"{key}_{self.vin}"
        if active:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=key,
                translation_placeholders={"vehicle": self.title, "vin": self.vin[-6:]},
                learn_more_url="https://eu-data-act.drivesomethinggreater.com",
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    # -- state ---------------------------------------------------------------------

    @property
    def title(self) -> str:
        return self.nickname or f"Cupra {self.vin[-6:]}"

    @property
    def ola_available(self) -> bool:
        return self.ola is not None and self.ola_status == "ok"

    def _build(self) -> dict[str, Any]:
        state = parser.extract_state(self.fields)
        ola_state = parser.extract_ola_state(self.ola_raw) if self.ola_raw else {}
        ola_fresh = self.ola_status == "ok"
        for key, value in ola_state.items():
            if ola_fresh or key not in state:
                state[key] = value
        state = parser.finalize_state(state)

        model = self.model_option if self.model_option != MODEL_AUTO else guess_model(self.nickname, self.config_entry.data.get("model"))
        model_info = MODELS.get(model or "", {})
        powertrain = self.powertrain_option if self.powertrain_option != "auto" else None
        powertrain = powertrain or parser.detect_powertrain(state, self.fields) or model_info.get("powertrain")
        el_range, fuel_range = parser.electric_and_fuel_ranges(state, powertrain)
        state["range_electric"] = el_range
        state["range_fuel"] = fuel_range

        last_seen = self.captured_at
        if self.ola_updated and ola_fresh and (last_seen is None or self.ola_updated > last_seen):
            last_seen = self.ola_updated
        return {
            "state": state,
            "model": model,
            "model_name": model_info.get("name"),
            "body": model_info.get("body", "hatch"),
            "powertrain": powertrain,
            "last_seen": last_seen,
            "stale": last_seen is None or _now() - last_seen > STALE_AFTER,
            "euda": {
                "status": self.euda_status,
                "error": self.euda_error,
                "dataset": self.last_dataset,
                "captured_at": self.captured_at,
                "field_count": len(self.fields),
            },
            "ola": {
                "status": self.ola_status,
                "error": self.ola_error,
                "updated": self.ola_updated,
            },
            "last_command": self.last_command,
        }

    # -- commands --------------------------------------------------------------------

    async def async_command(self, command: str, **kwargs: Any) -> None:
        if not self.ola:
            raise HomeAssistantError("Remote commands need the My Cupra connection (enable it in the options)")
        if self.ola_status == "blocked":
            raise HomeAssistantError("My Cupra API is currently blocked by VW (App Check) – commands are unavailable")
        try:
            if command == "lock":
                await self.ola.async_lock(self.vin, True)
            elif command == "unlock":
                await self.ola.async_lock(self.vin, False)
            elif command == "climate_on":
                await self.ola.async_climate(self.vin, True, kwargs.get("temperature") or (self.data or {}).get("state", {}).get("climate_target_temp"))
            elif command == "climate_off":
                await self.ola.async_climate(self.vin, False)
            elif command == "charging_on":
                await self.ola.async_charging(self.vin, True)
            elif command == "charging_off":
                await self.ola.async_charging(self.vin, False)
            elif command == "window_heating_on":
                await self.ola.async_window_heating(self.vin, True)
            elif command == "window_heating_off":
                await self.ola.async_window_heating(self.vin, False)
            elif command in ("flash", "honk_flash"):
                st = (self.data or {}).get("state", {})
                lat, lon = st.get("latitude"), st.get("longitude")
                if lat is None or lon is None:
                    raise HomeAssistantError("Vehicle position unknown – honk/flash needs it")
                await self.ola.async_honk_flash(self.vin, lat, lon, command == "honk_flash")
            elif command == "wakeup":
                await self.ola.async_wakeup(self.vin)
            else:
                raise HomeAssistantError(f"Unknown command {command}")
        except OlaBlockedError as err:
            self.ola_status = "blocked"
            self._issue("ola_blocked", True)
            raise HomeAssistantError("My Cupra API refused the command (App Check)") from err
        except OlaThrottledError as err:
            raise HomeAssistantError(str(err)) from err
        except CupraApiError as err:
            raise HomeAssistantError(f"Command failed: {err}") from err
        self.last_command = {"command": command, "at": _now().isoformat()}
        self._ola_next = _now() + timedelta(seconds=45)
        self.async_update_listeners()
        async_call_later(self.hass, 50, self._delayed_refresh)

    async def _delayed_refresh(self, _now: datetime) -> None:
        await self.async_request_refresh()

    async def async_force_refresh(self) -> None:
        self._ola_next = _now()
        await self.async_request_refresh()
