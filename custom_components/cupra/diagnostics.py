"""Diagnostics: raw portal fields + parsed state (VIN, position and tokens redacted)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import CupraConfigEntry
from .const import CONF_APPCHECK, CONF_SPIN, CONF_VIN

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, CONF_VIN, CONF_SPIN, CONF_APPCHECK, "latitude", "longitude", "lat", "lon", "vin", "userId", "user_id"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: CupraConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    data = c.data or {}
    return {
        "entry": async_redact_data({**entry.data, **entry.options}, TO_REDACT),
        "model": data.get("model"),
        "powertrain": data.get("powertrain"),
        "euda": {k: str(v) for k, v in data.get("euda", {}).items()},
        "ola": {k: str(v) for k, v in data.get("ola", {}).items()},
        "state": async_redact_data(data.get("state", {}), TO_REDACT),
        "euda_fields": {k: [v.value, v.captured_at.isoformat() if v.captured_at else None] for k, v in sorted(c.fields.items())},
        "ola_raw": async_redact_data(c.ola_raw, TO_REDACT),
    }
