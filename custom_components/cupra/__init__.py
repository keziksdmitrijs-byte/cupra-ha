"""Cupra vehicles for Home Assistant (EU Data Act + My Cupra)."""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import CARD_FILENAME, DOMAIN, FRONTEND_URL, PLATFORMS, VERSION
from .coordinator import CupraCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type CupraConfigEntry = ConfigEntry[CupraCoordinator]

SERVICE_REFRESH = "refresh"
SERVICE_CLIMATE = "start_climate"
_COMMANDS = ("lock", "unlock", "climate_on", "climate_off", "charging_on", "charging_off", "flash", "honk_flash", "wakeup")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    await _async_register_frontend(hass)

    def _coordinators(call: ServiceCall) -> list[CupraCoordinator]:
        device_ids = call.data.get(ATTR_DEVICE_ID) or []
        reg = dr.async_get(hass)
        result = []
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            coord: CupraCoordinator = entry.runtime_data
            if not device_ids:
                result.append(coord)
                continue
            for dev_id in device_ids:
                dev = reg.async_get(dev_id)
                if dev and (DOMAIN, coord.vin) in dev.identifiers:
                    result.append(coord)
        if not result:
            raise HomeAssistantError("No matching Cupra vehicle")
        return result

    async def _refresh(call: ServiceCall) -> None:
        for coord in _coordinators(call):
            await coord.async_force_refresh()

    async def _climate(call: ServiceCall) -> None:
        for coord in _coordinators(call):
            await coord.async_command("climate_on", temperature=call.data.get("temperature"))

    async def _command(call: ServiceCall) -> None:
        for coord in _coordinators(call):
            await coord.async_command(call.data["command"])

    device_schema = {vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _refresh, schema=vol.Schema(device_schema))
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLIMATE,
        _climate,
        schema=vol.Schema({**device_schema, vol.Optional("temperature"): vol.All(vol.Coerce(float), vol.Range(min=16, max=30))}),
    )
    hass.services.async_register(
        DOMAIN, "command", _command, schema=vol.Schema({**device_schema, vol.Required("command"): vol.In(_COMMANDS)})
    )
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the Lovelace card from the integration and load it on every dashboard."""
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    path = Path(__file__).parent / "frontend"
    try:
        await hass.http.async_register_static_paths([StaticPathConfig(FRONTEND_URL, str(path), False)])
    except RuntimeError:
        pass  # already registered (integration reload)
    try:
        add_extra_js_url(hass, f"{FRONTEND_URL}/{CARD_FILENAME}?v={VERSION}")
    except KeyError:  # frontend not loaded (e.g. headless test instance)
        _LOGGER.debug("Frontend not loaded; card not registered")


async def async_setup_entry(hass: HomeAssistant, entry: CupraConfigEntry) -> bool:
    coordinator = CupraCoordinator(hass, entry)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: CupraConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: CupraConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
