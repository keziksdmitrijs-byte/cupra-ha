"""Config flow for Cupra."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api_euda import CupraApiError, CupraAuthError, EudaClient
from .const import (
    CONF_APPCHECK,
    CONF_COUNTRY,
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
    POWERTRAINS,
)
from .coordinator import guess_model

_LOGGER = logging.getLogger(__name__)

_MODEL_SELECT = SelectSelector(
    SelectSelectorConfig(
        options=[MODEL_AUTO, *MODELS],
        translation_key="model",
        mode=SelectSelectorMode.DROPDOWN,
    )
)
_PT_SELECT = SelectSelector(SelectSelectorConfig(options=list(POWERTRAINS), translation_key="powertrain", mode=SelectSelectorMode.LIST))
_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class CupraConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict[str, Any] = {}
        self._vehicles: list[dict[str, str]] = []
        self._vehicle: dict[str, str] | None = None

    async def _login(self, data: dict[str, Any]) -> list[dict[str, str]]:
        session = async_create_clientsession(self.hass, cookie_jar=aiohttp.CookieJar())
        client = EudaClient(
            session,
            data[CONF_EMAIL],
            data[CONF_PASSWORD],
            country=data.get(CONF_COUNTRY, DEFAULT_COUNTRY),
            language=data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
        )
        await client.async_login()
        return await client.async_list_vehicles()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._vehicles = await self._login(user_input)
            except CupraAuthError as err:
                _LOGGER.debug("Login failed: %s", err)
                errors["base"] = "invalid_auth"
            except CupraApiError as err:
                _LOGGER.warning("Cupra portal unavailable: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not self._vehicles:
                    errors["base"] = "no_vehicles"
                else:
                    self._creds = user_input
                    if len(self._vehicles) == 1:
                        self._vehicle = self._vehicles[0]
                        return await self.async_step_model()
                    return await self.async_step_vehicle()
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=(user_input or {}).get(CONF_EMAIL, "")): str,
                vol.Required(CONF_PASSWORD): _PASSWORD,
                vol.Optional(CONF_USE_OLA, default=True): BooleanSelector(),
                vol.Optional(CONF_COUNTRY, default=DEFAULT_COUNTRY): str,
                vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_vehicle(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._vehicle = next(v for v in self._vehicles if v["vin"] == user_input[CONF_VIN])
            return await self.async_step_model()
        options = [{"value": v["vin"], "label": f"{v.get('nickname') or v.get('model') or 'Cupra'} (…{v['vin'][-6:]})"} for v in self._vehicles]
        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema({vol.Required(CONF_VIN): SelectSelector(SelectSelectorConfig(options=options))}),
        )

    async def async_step_model(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._vehicle is not None
        vin = self._vehicle["vin"]
        await self.async_set_unique_id(vin)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            nickname = self._vehicle.get("nickname") or (MODELS.get(user_input[CONF_MODEL], {}).get("name")) or f"Cupra {vin[-6:]}"
            return self.async_create_entry(
                title=nickname,
                data={
                    CONF_EMAIL: self._creds[CONF_EMAIL],
                    CONF_PASSWORD: self._creds[CONF_PASSWORD],
                    CONF_VIN: vin,
                    CONF_NICKNAME: nickname,
                    "model": self._vehicle.get("model"),
                },
                options={
                    CONF_USE_OLA: self._creds.get(CONF_USE_OLA, True),
                    CONF_COUNTRY: self._creds.get(CONF_COUNTRY, DEFAULT_COUNTRY),
                    CONF_LANGUAGE: self._creds.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_POWERTRAIN: user_input[CONF_POWERTRAIN],
                },
            )
        guess = guess_model(self._vehicle.get("nickname"), self._vehicle.get("model")) or MODEL_AUTO
        return self.async_show_form(
            step_id="model",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=guess): _MODEL_SELECT,
                    vol.Required(CONF_POWERTRAIN, default="auto"): _PT_SELECT,
                }
            ),
            description_placeholders={"vehicle": self._vehicle.get("nickname") or vin[-6:]},
        )

    # -- reauth ------------------------------------------------------------------

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **entry.options, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                await self._login(data)
            except CupraAuthError:
                errors["base"] = "invalid_auth"
            except CupraApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD}),
            errors=errors,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return CupraOptionsFlow()


class CupraOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        o = {**self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_MODEL, default=o.get(CONF_MODEL, MODEL_AUTO)): _MODEL_SELECT,
                vol.Required(CONF_POWERTRAIN, default=o.get(CONF_POWERTRAIN, "auto")): _PT_SELECT,
                vol.Required(CONF_USE_OLA, default=o.get(CONF_USE_OLA, True)): BooleanSelector(),
                vol.Optional(CONF_SPIN, description={"suggested_value": o.get(CONF_SPIN)}): _PASSWORD,
                vol.Required(CONF_OLA_INTERVAL, default=o.get(CONF_OLA_INTERVAL, DEFAULT_OLA_INTERVAL)): NumberSelector(
                    NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_APPCHECK, description={"suggested_value": o.get(CONF_APPCHECK)}): TextSelector(
                    TextSelectorConfig(multiline=True)
                ),
                vol.Required(CONF_COUNTRY, default=o.get(CONF_COUNTRY, DEFAULT_COUNTRY)): str,
                vol.Required(CONF_LANGUAGE, default=o.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
