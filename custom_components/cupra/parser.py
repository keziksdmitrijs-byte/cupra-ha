"""Pure-Python data layer: EU Data Act datasets + My Cupra (OLA) → one vehicle state.

No Home Assistant imports, so it can be unit-tested offline.

Field names, unit conversions and state encodings were worked out from the
VW Group EU Data Act data dictionary and the field research done in
HA_VAG-EU-Data-Act (MIT, (c) 2026 Jernej Fijačko) and pycupra (Apache-2.0).
See THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

_DICT_PATH = Path(__file__).with_name("data_dictionary.json")

POWERTRAIN_EV = "ev"
POWERTRAIN_PHEV = "phev"
POWERTRAIN_ICE = "ice"


@lru_cache(maxsize=1)
def load_dictionary() -> dict[str, dict[str, str]]:
    """key (UUID) → {"n": field name, "t": type}."""
    try:
        return json.loads(_DICT_PATH.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")
_DUR_RE = re.compile(r"^(-?\d+(?:\.\d+)?)s$")

# "No reading" sentinels the portal sends instead of omitting a field.
_SENTINELS = frozenset({2**16 - 1, 2**31 - 1, 2**32 - 2, 2**32 - 1})


def parse_value(raw: Any, type_hint: str = "") -> Any:
    """Coerce a raw portal string into bool / int / float / str."""
    if raw is None:
        return None
    if isinstance(raw, (bool, int, float)):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    low = s.lower()
    if type_hint == "boolean" or low in ("true", "false"):
        return low == "true"
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    m = _DUR_RE.match(s)
    if m:
        return float(m.group(1))
    return s


def is_sentinel(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value in _SENTINELS


def parse_timestamp(raw: Any) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip().replace("Z", "+00:00")
    # Python < 3.11 cannot parse 3-digit fractions with offsets in all forms.
    s = re.sub(r"\.(\d{1,6})\d*(?=[+-]\d{2}:?\d{2}$|$)", lambda m: "." + m.group(1).ljust(6, "0"), s)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# ---------------------------------------------------------------------------
# Dataset → flat field map
# ---------------------------------------------------------------------------

_CAPTURE_FIELDS = (
    "car_captured_utc_timestamp",
    "car_captured_time",
    "profile_state_report.car_captured_time",
    "timestamp",
)

# Model-specific aliases for the same signal.
_ALIASES = {
    "remaining_climatisation_time": "remaining_climate_time",
    "charging_plug1_connectionstate": "plug_state",
}


@dataclass
class FieldValue:
    value: Any
    captured_at: datetime | None = None


def parse_dataset(payload: dict) -> tuple[dict[str, FieldValue], datetime | None]:
    """Turn one Data Act JSON (``{"Data": [...]}``) into ``{field_name: FieldValue}``.

    When a field occurs several times, a real reading beats a sentinel/empty
    slot; among real readings the larger one wins for the odometer.
    """
    dictionary = load_dictionary()
    raw: dict[str, list[tuple[Any, datetime | None]]] = {}
    for item in payload.get("Data", []) or []:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or ""
        meta = dictionary.get(key, {})
        name = item.get("dataFieldName") or meta.get("n") or key
        if not name:
            continue
        name = _ALIASES.get(name, name)
        value = parse_value(item.get("value"), meta.get("t", ""))
        ts = parse_timestamp(item.get("timestampUtc"))
        raw.setdefault(name, []).append((value, ts))

    captured: datetime | None = None
    for cf in _CAPTURE_FIELDS:
        for value, _ in raw.get(cf, []):
            ts = parse_timestamp(value) if isinstance(value, str) else None
            if ts and (captured is None or ts > captured):
                captured = ts
    for slots in raw.values():
        for _, ts in slots:
            if ts and (captured is None or ts > captured):
                captured = ts

    out: dict[str, FieldValue] = {}
    for name, slots in raw.items():
        good = [(v, ts) for v, ts in slots if v is not None and not is_sentinel(v)]
        if not good:
            continue
        if name in ("mileage", "mileage.value"):
            v, ts = max(good, key=lambda s: s[0] if isinstance(s[0], (int, float)) else -1)
        else:
            v, ts = max(good, key=lambda s: s[1] or datetime.min.replace(tzinfo=UTC))
        out[name] = FieldValue(v, ts or captured)
    return out, captured


def merge_fields(
    old: dict[str, FieldValue], new: dict[str, FieldValue]
) -> dict[str, FieldValue]:
    """Sticky merge: a partial snapshot must not erase what we already know."""
    merged = dict(old)
    for name, fv in new.items():
        prev = merged.get(name)
        if prev is None or prev.captured_at is None or fv.captured_at is None or fv.captured_at >= prev.captured_at:
            merged[name] = fv
    return merged


# ---------------------------------------------------------------------------
# Decoders
# ---------------------------------------------------------------------------


def _num(v: Any) -> float | int | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() and abs(f) < 1e12 else f


def _div10(v: Any) -> float | None:
    n = _num(v)
    return None if n is None else round(n / 10, 1)


def _dk_to_c(v: Any) -> float | None:
    n = _num(v)
    if n is None:
        return None
    return round(n / 10 - 273.15, 1)


def _temp_auto(v: Any) -> float | None:
    """Outside temperature arrives in °C, K or deci-K depending on model."""
    n = _num(v)
    if n is None:
        return None
    if n > 1000:
        return round(n / 10 - 273.15, 1)
    if n > 150:
        return round(n - 273.15, 1)
    return round(n, 1)


def _sec_to_min(v: Any) -> float | None:
    n = _num(v)
    return None if n is None else round(n / 60)


def _pct(v: Any) -> float | None:
    n = _num(v)
    if n is None or n < 0 or n > 100:
        return None
    return n


def _pos(v: Any) -> float | None:
    n = _num(v)
    return None if n is None else n


def _tyre(v: Any) -> float | None:
    n = _num(v)
    if n is None or n in (0, 1):
        return None  # 0 = unsupported, 1 = invalid
    if n > 50:  # reported in 1/100 bar or kPa-ish integers
        n = n / 100
    return round(n, 2)


def _open_enc(v: Any) -> bool | None:
    """Dominant VW door/window encoding: 2 = active (open/locked), 3 = inactive."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        if v in (0, 1):
            return None
        return v == 2
    if isinstance(v, str):
        t = v.strip().lower()
        if t in ("open", "opened", "true", "on", "locked", "connected"):
            return True
        if t in ("closed", "false", "off", "unlocked", "disconnected"):
            return False
    return None


def _onoff(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v == 1
    if isinstance(v, str):
        t = v.strip().lower()
        if t in ("on", "true", "active", "1"):
            return True
        if t in ("off", "false", "inactive", "0"):
            return False
    return None


def _plug(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        t = v.strip().lower()
        if "disconnected" in t:
            return False
        if "connected" in t:
            return True
    return None


def _lock_str(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        t = v.strip().lower()
        if t == "locked":
            return True
        if t == "unlocked":
            return False
    return _open_enc(v)


def _charging_from_state(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        t = v.strip().lower()
        return t in ("charging", "charge", "chargepurposereachedandconservation") or t.startswith("charging")
    return None


def _str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


@dataclass(frozen=True)
class Spec:
    """One canonical signal and the portal fields that can carry it (in priority order)."""

    key: str
    candidates: tuple[tuple[str, Callable[[Any], Any]], ...]


def _c(*pairs) -> tuple[tuple[str, Callable[[Any], Any]], ...]:
    return tuple(pairs)


SPECS: tuple[Spec, ...] = (
    # --- energy -----------------------------------------------------------
    Spec("soc", _c(("state_of_charge", _pct), ("battery_state_report.soc", _pct),
                   ("battery_charging_status_soc", _pct), ("battery_level_HV.value", _pct))),
    Spec("target_soc", _c(("settings.target_soc", _pct), ("active_target_soc", _pct))),
    Spec("fuel_level", _c(("fuel_level_current_level", _pct), ("fuel_level.value", _pct),
                          ("fuel_level.fuel_level", _pct), ("fuel_level", _pct), ("Fuel level", _pct))),
    Spec("range_total", _c(("cruising_range_combined", _pos))),
    Spec("range_primary", _c(("cruising_range_primary_engine", _pos), ("estimatedcruisingrangeprimary.value", _pos),
                             ("value_of_the_primary_range", _pos), ("range.value", _pos), ("range", _pos))),
    Spec("range_secondary", _c(("cruising_range_secondary_engine", _pos), ("estimatedcruisingrangesecondary.value", _pos))),
    Spec("mileage", _c(("mileage", _pos), ("mileage.value", _pos))),
    # --- charging ---------------------------------------------------------
    Spec("charging_state", _c(("charging_state", _str), ("charging_state_report.current_charge_state", _str),
                              ("Current Charge State", _str))),
    Spec("charge_power", _c(("battery_state_report.charge_power", _pos), ("charging_power", _div10))),
    Spec("charge_rate", _c(("battery_state_report.charge_rate", _pos), ("actual_charge_rate", _div10))),
    Spec("charge_remaining_min", _c(("battery_state_report.remaining_charging_time_complete", _sec_to_min),
                                    ("remaining_charging_time", _pos))),
    Spec("plug_connected", _c(("plug_state", _plug), ("plug_connection_state", _plug),
                              ("Plug Connection State", _plug))),
    Spec("charging_flag", _c(("charging", _onoff))),
    # --- body -------------------------------------------------------------
    Spec("locked", _c(("locked", _onoff), ("lock_state", _lock_str))),
    Spec("door_fl", _c(("open_state_front_left_door", _open_enc))),
    Spec("door_fr", _c(("open_state_front_right_door", _open_enc))),
    Spec("door_rl", _c(("open_state_rear_left_door", _open_enc))),
    Spec("door_rr", _c(("open_state_rear_right_door", _open_enc))),
    Spec("trunk", _c(("open_state_tailgate", _open_enc), ("trunk.open", _onoff))),
    Spec("hood", _c(("open_state_front_engine_bonnet", _open_enc), ("enginehood.open", _onoff))),
    Spec("window_fl", _c(("state_front_left_door_window_lifter", _open_enc))),
    Spec("window_fr", _c(("state_front_right_door_window_lifter", _open_enc))),
    Spec("window_rl", _c(("state_rear_left_door_window_lifter", _open_enc))),
    Spec("window_rr", _c(("state_rear_right_door_window_lifter", _open_enc))),
    Spec("sunroof", _c(("state_sunroof_motor_hood_1", _open_enc), ("sunrooffront.open", _onoff))),
    Spec("any_open", _c(("open", _onoff))),
    Spec("parking_brake", _c(("parking_brake", _onoff), ("parking_brake.parking_brake", _onoff))),
    Spec("parking_lights", _c(("parking_lights", lambda v: None if v in (0, 1) else v in (3, 4, 5)
                               if isinstance(v, int) and not isinstance(v, bool) else _onoff(v)))),
    # --- climate / environment --------------------------------------------
    Spec("outside_temp", _c(("outside_temperature", _dk_to_c), ("outdoor_temperature", _temp_auto),
                            ("outdoor_temperature.outdoor_temperature", _temp_auto),
                            ("outsideTemperatureIndication", _temp_auto))),
    Spec("climate_remaining_min", _c(("remaining_climate_time", _sec_to_min))),
    Spec("battery_12v", _c(("boardnetBatteryVoltageIndication", lambda v: (_num(v) / 1000 if (_num(v) or 0) > 100 else _num(v))))),
    # --- service ----------------------------------------------------------
    Spec("inspection_days", _c(("maintenance_interval__time_until_inspection", _num), ("Time to next inspection", _num))),
    Spec("inspection_km", _c(("maintenance_interval_distance_until_inspection", _num), ("inspectionDistance", _num),
                             ("Distance to next inspection", _num))),
    Spec("oil_days", _c(("maintenance_interval__time_until_oil_change", _num), ("Time to next oil inspection", _num))),
    Spec("oil_km", _c(("maintenance_interval_distance_until_oil_change", _num), ("Distance to next oil inspection", _num))),
    Spec("oil_level", _c(("oil_level_actual_level", _num))),
    Spec("tyre_fl", _c(("tyre_pressure_actual_front_left", _tyre))),
    Spec("tyre_fr", _c(("tyre_pressure_actual_front_right", _tyre))),
    Spec("tyre_rl", _c(("tyre_pressure_actual_rear_left", _tyre))),
    Spec("tyre_rr", _c(("tyre_pressure_actual_rear_right", _tyre))),
    # --- trips ------------------------------------------------------------
    Spec("trip_short_km", _c(("short_term_data_mileage", _num))),
    Spec("trip_short_fuel", _c(("short_term_data_average_fuel_consumption", _div10))),
    Spec("trip_short_electric", _c(("short_term_data_average_electr_engine_consumption", _div10))),
    Spec("trip_long_km", _c(("long_term_data_mileage", _num))),
    Spec("trip_long_fuel", _c(("long_term_data_average_fuel_consumption", _div10))),
    Spec("trip_long_electric", _c(("long_term_data_average_electr_engine_consumption", _div10))),
    Spec("trip_long_speed", _c(("long_term_data_average_speed", _num))),
)

SPEC_KEYS = tuple(s.key for s in SPECS)

DOOR_KEYS = ("door_fl", "door_fr", "door_rl", "door_rr", "trunk", "hood")
WINDOW_KEYS = ("window_fl", "window_fr", "window_rl", "window_rr", "sunroof")


def extract_state(fields: dict[str, FieldValue]) -> dict[str, Any]:
    """Resolve every canonical signal from the merged Data Act fields."""
    state: dict[str, Any] = {}
    for spec in SPECS:
        for name, decode in spec.candidates:
            fv = fields.get(name)
            if fv is None:
                continue
            try:
                value = decode(fv.value)
            except (TypeError, ValueError, ZeroDivisionError):
                value = None
            if value is not None:
                state[spec.key] = value
                break
    return state


# ---------------------------------------------------------------------------
# My Cupra (OLA) responses → canonical keys
# ---------------------------------------------------------------------------


def _truthy(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        t = v.lower()
        if t in ("true", "open", "opened", "locked", "on"):
            return True
        if t in ("false", "closed", "unlocked", "off"):
            return False
    return None


def extract_ola_state(ola: dict[str, Any]) -> dict[str, Any]:
    """Map the raw OLA endpoint payloads (as fetched by api_ola) to canonical keys."""
    s: dict[str, Any] = {}
    status = ola.get("status") or {}
    doors = status.get("doors") or {}
    door_map = {"frontLeft": "door_fl", "frontRight": "door_fr", "rearLeft": "door_rl", "rearRight": "door_rr"}
    locks: list[bool] = []
    for src, dst in door_map.items():
        d = doors.get(src)
        if isinstance(d, dict):
            o = _truthy(d.get("open"))
            if o is not None:
                s[dst] = o
            lk = _truthy(d.get("locked"))
            if lk is not None:
                locks.append(lk)
    if locks:
        s["locked"] = all(locks)
    for src, dst in (("trunk", "trunk"), ("hood", "hood")):
        d = status.get(src) or doors.get(src)
        if isinstance(d, dict):
            o = _truthy(d.get("open"))
            if o is not None:
                s[dst] = o
    windows = status.get("windows") or {}
    win_map = {"frontLeft": "window_fl", "frontRight": "window_fr", "rearLeft": "window_rl", "rearRight": "window_rr"}
    for src, dst in win_map.items():
        w = windows.get(src)
        if isinstance(w, str) and w:
            s[dst] = w.lower() != "closed"
    sunroof = status.get("sunroof") or windows.get("sunroof")
    if isinstance(sunroof, str):
        s["sunroof"] = sunroof.lower() != "closed"
    if isinstance(status.get("updatedAt"), str):
        s["ola_updated_at"] = status["updatedAt"]

    mycar = ola.get("mycar") or {}
    engines = mycar.get("engines") or {}
    primary = engines.get("primary") or {}
    secondary = engines.get("secondary") or {}
    fuel_types = [str(e.get("fuelType", "")).lower() for e in (primary, secondary) if e]
    if fuel_types:
        s["ola_fuel_types"] = fuel_types
    for eng, rkey in ((primary, "range_primary"), (secondary, "range_secondary")):
        if not eng:
            continue
        ft = str(eng.get("fuelType", "")).lower()
        lvl = _num(eng.get("levelPct"))
        if lvl is not None:
            s["soc" if ft == "electric" else "fuel_level"] = lvl
        rng = _num(eng.get("rangeKm"))
        if rng is not None:
            s[rkey] = rng

    mileage = ola.get("mileage") or {}
    if _num(mileage.get("mileageKm")) is not None:
        s["mileage"] = _num(mileage["mileageKm"])

    ranges = ola.get("ranges") or []
    if isinstance(ranges, list):
        total = sum(_num(r.get("rangeKm")) or 0 for r in ranges if isinstance(r, dict))
        if total:
            s["range_total"] = total

    charging = (ola.get("charging") or {}).get("status") or {}
    battery = charging.get("battery") or {}
    if _num(battery.get("currentSocPercentage")) is not None:
        s["soc"] = _num(battery["currentSocPercentage"])
    ch = charging.get("charging") or {}
    if ch.get("state"):
        s["charging_state"] = str(ch["state"])
    if _num(ch.get("chargePowerInKw")) is not None:
        s["charge_power"] = _num(ch["chargePowerInKw"])
    if _num(ch.get("remainingTimeInMinutes")) is not None:
        s["charge_remaining_min"] = _num(ch["remainingTimeInMinutes"])
    plug = charging.get("plug") or {}
    if plug.get("connection"):
        s["plug_connected"] = str(plug["connection"]).lower() == "connected"
    info = (ola.get("charging") or {}).get("info") or {}
    settings = info.get("settings") or {}
    if _num(settings.get("targetSoc")) is not None:
        s["target_soc"] = _num(settings["targetSoc"])

    climater = ola.get("climater") or {}
    cstatus = (climater.get("status") or {}).get("climatisationStatus") or {}
    cstate = cstatus.get("climatisationState")
    if isinstance(cstate, str):
        s["climate_state"] = cstate
        s["climate_on"] = cstate.lower() not in ("off", "invalid", "")
    if _num(cstatus.get("remainingClimatisationTimeInMinutes")) is not None:
        s["climate_remaining_min"] = _num(cstatus["remainingClimatisationTimeInMinutes"])
    csettings = climater.get("settings") or {}
    if _num(csettings.get("targetTemperatureInCelsius")) is not None:
        s["climate_target_temp"] = _num(csettings["targetTemperatureInCelsius"])

    pos = ola.get("position") or {}
    if _num(pos.get("lat")) is not None and _num(pos.get("lon")) is not None:
        s["latitude"] = _num(pos["lat"])
        s["longitude"] = _num(pos["lon"])
    if ola.get("moving") is True:
        s["moving"] = True
    return s


# ---------------------------------------------------------------------------
# Derived values
# ---------------------------------------------------------------------------


def detect_powertrain(state: dict[str, Any], fields: dict[str, FieldValue] | None = None) -> str | None:
    fuel_types = state.get("ola_fuel_types") or []
    has_el = "electric" in fuel_types
    has_fuel = any(ft in ("gasoline", "petrol", "diesel", "cng", "fuel") for ft in fuel_types)
    if fuel_types:
        if has_el and has_fuel:
            return POWERTRAIN_PHEV
        if has_el:
            return POWERTRAIN_EV
        if has_fuel:
            return POWERTRAIN_ICE
    has_soc = state.get("soc") is not None
    has_fuel_lvl = state.get("fuel_level") is not None
    if has_soc and has_fuel_lvl:
        return POWERTRAIN_PHEV
    if has_soc:
        return POWERTRAIN_EV
    if has_fuel_lvl:
        return POWERTRAIN_ICE
    if fields:
        names = set(fields)
        if any(n.startswith("battery_state_report.") for n in names):
            return POWERTRAIN_EV
    return None


def finalize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Fill derived values: charging, open summaries, total range."""
    s = dict(state)
    flag = s.pop("charging_flag", None)
    charging = _charging_from_state(s.get("charging_state"))
    if charging is None:
        charging = flag
    if charging is None and isinstance(s.get("charge_power"), (int, float)):
        charging = s["charge_power"] > 0
    if charging is not None:
        s["charging"] = charging
    doors = [s[k] for k in DOOR_KEYS if isinstance(s.get(k), bool)]
    if doors:
        s["doors_open"] = any(doors)
    elif isinstance(s.get("any_open"), bool):
        s["doors_open"] = s["any_open"]
    windows = [s[k] for k in WINDOW_KEYS if isinstance(s.get(k), bool)]
    if windows:
        s["windows_open"] = any(windows)
    if s.get("range_total") is None:
        parts = [s.get("range_primary"), s.get("range_secondary")]
        nums = [p for p in parts if isinstance(p, (int, float))]
        if nums:
            s["range_total"] = sum(nums)
    if s.get("climate_on") is None and isinstance(s.get("climate_remaining_min"), (int, float)):
        s["climate_on"] = s["climate_remaining_min"] > 0
    return s


def electric_and_fuel_ranges(state: dict[str, Any], powertrain: str | None) -> tuple[float | None, float | None]:
    """Split primary/secondary ranges into (electric, fuel) for display."""
    p, sec = state.get("range_primary"), state.get("range_secondary")
    if powertrain == POWERTRAIN_EV:
        return (p if p is not None else state.get("range_total")), None
    if powertrain == POWERTRAIN_ICE:
        return None, (p if p is not None else state.get("range_total"))
    # PHEV: VW reports the combustion engine as primary, the e-motor as secondary.
    fuel_types = state.get("ola_fuel_types") or []
    if fuel_types and fuel_types[0] == "electric":
        return p, sec
    return sec, p
