"""Sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import CupraConfigEntry
from .const import DOMAIN
from .coordinator import CupraCoordinator
from .entity import CupraEntity, add_dynamic

M = SensorStateClass.MEASUREMENT
KM = UnitOfLength.KILOMETERS


@dataclass(frozen=True, kw_only=True)
class CupraSensorDescription(SensorEntityDescription):
    diagnostic: bool = False


def _d(key: str, **kw: Any) -> CupraSensorDescription:
    return CupraSensorDescription(key=key, translation_key=key, **kw)


SENSORS: tuple[CupraSensorDescription, ...] = (
    _d("soc", device_class=SensorDeviceClass.BATTERY, native_unit_of_measurement=PERCENTAGE, state_class=M),
    _d("target_soc", native_unit_of_measurement=PERCENTAGE, state_class=M, icon="mdi:battery-charging-80"),
    _d("fuel_level", native_unit_of_measurement=PERCENTAGE, state_class=M, icon="mdi:gas-station"),
    _d("range_electric", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=KM, state_class=M, icon="mdi:ev-station", suggested_display_precision=0),
    _d("range_fuel", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=KM, state_class=M, icon="mdi:gas-station", suggested_display_precision=0),
    _d("range_total", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=KM, state_class=M, icon="mdi:map-marker-distance", suggested_display_precision=0),
    _d("mileage", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=KM, state_class=SensorStateClass.TOTAL_INCREASING, icon="mdi:counter", suggested_display_precision=0),
    _d("charging_state", icon="mdi:ev-station"),
    _d("charge_power", device_class=SensorDeviceClass.POWER, native_unit_of_measurement=UnitOfPower.KILO_WATT, state_class=M),
    _d("charge_rate", native_unit_of_measurement="km/h", state_class=M, icon="mdi:speedometer"),
    _d("charge_remaining_min", device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES, state_class=M, icon="mdi:battery-clock"),
    _d("outside_temp", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=M),
    _d("climate_remaining_min", device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES, state_class=M, icon="mdi:fan-clock"),
    _d("climate_target_temp", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, icon="mdi:thermostat"),
    _d("battery_12v", device_class=SensorDeviceClass.VOLTAGE, native_unit_of_measurement=UnitOfElectricPotential.VOLT, state_class=M, suggested_display_precision=1, entity_category=EntityCategory.DIAGNOSTIC),
    _d("inspection_days", native_unit_of_measurement=UnitOfTime.DAYS, state_class=M, icon="mdi:car-wrench"),
    _d("inspection_km", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=KM, state_class=M, icon="mdi:car-wrench"),
    _d("oil_days", native_unit_of_measurement=UnitOfTime.DAYS, state_class=M, icon="mdi:oil"),
    _d("oil_km", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=KM, state_class=M, icon="mdi:oil"),
    _d("oil_level", native_unit_of_measurement=PERCENTAGE, state_class=M, icon="mdi:oil-level"),
    _d("tyre_fl", device_class=SensorDeviceClass.PRESSURE, native_unit_of_measurement=UnitOfPressure.BAR, state_class=M, suggested_display_precision=1),
    _d("tyre_fr", device_class=SensorDeviceClass.PRESSURE, native_unit_of_measurement=UnitOfPressure.BAR, state_class=M, suggested_display_precision=1),
    _d("tyre_rl", device_class=SensorDeviceClass.PRESSURE, native_unit_of_measurement=UnitOfPressure.BAR, state_class=M, suggested_display_precision=1),
    _d("tyre_rr", device_class=SensorDeviceClass.PRESSURE, native_unit_of_measurement=UnitOfPressure.BAR, state_class=M, suggested_display_precision=1),
    _d("trip_short_km", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=KM, state_class=M, icon="mdi:map-marker-path"),
    _d("trip_short_fuel", native_unit_of_measurement="L/100km", state_class=M, icon="mdi:fuel"),
    _d("trip_short_electric", native_unit_of_measurement="kWh/100km", state_class=M, icon="mdi:flash"),
    _d("trip_long_km", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement=KM, state_class=M, icon="mdi:map-marker-path"),
    _d("trip_long_fuel", native_unit_of_measurement="L/100km", state_class=M, icon="mdi:fuel"),
    _d("trip_long_electric", native_unit_of_measurement="kWh/100km", state_class=M, icon="mdi:flash"),
    _d("trip_long_speed", device_class=SensorDeviceClass.SPEED, native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR, state_class=M),
)
_BY_KEY = {d.key: d for d in SENSORS}


async def async_setup_entry(hass: HomeAssistant, entry: CupraConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([CupraVehicleSensor(coordinator), CupraLastSeenSensor(coordinator)])

    def factory(created: set[str]):
        state = (coordinator.data or {}).get("state", {})
        return [CupraSensor(coordinator, d) for d in SENSORS if d.key not in created and state.get(d.key) is not None]

    entry.async_on_unload(add_dynamic(hass, coordinator, async_add_entities, factory))


class CupraSensor(CupraEntity, SensorEntity):
    entity_description: CupraSensorDescription

    def __init__(self, coordinator: CupraCoordinator, description: CupraSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.state_data.get(self.key)


class CupraLastSeenSensor(CupraEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CupraCoordinator) -> None:
        super().__init__(coordinator, "last_seen")

    @property
    def native_value(self) -> datetime | None:
        return (self.coordinator.data or {}).get("last_seen")


class CupraVehicleSensor(CupraEntity, SensorEntity):
    """Summary entity; the Lovelace card reads everything from its attributes."""

    _attr_icon = "mdi:car-sports"
    _unrecorded_attributes = frozenset({"state", "entities", "sources", "model", "body", "powertrain", "model_name"})

    def __init__(self, coordinator: CupraCoordinator) -> None:
        super().__init__(coordinator, "vehicle")
        # Stable id regardless of HA language, so the card YAML in the README works.
        self.entity_id = f"sensor.{slugify(coordinator.title)}_vehicle"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["charging", "moving", "climatising", "open", "unlocked", "parked", "unknown"]

    @property
    def native_value(self) -> str:
        s = self.state_data
        if not s:
            return "unknown"
        if s.get("charging"):
            return "charging"
        if s.get("moving"):
            return "moving"
        if s.get("climate_on"):
            return "climatising"
        if s.get("doors_open") or s.get("windows_open"):
            return "open"
        if s.get("locked") is False:
            return "unlocked"
        return "parked"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _registry_changed(event) -> None:
            ent = er.async_get(self.hass).async_get(event.data.get("entity_id", ""))
            if event.data.get("action") == "remove" or (ent and ent.config_entry_id == self.coordinator.config_entry.entry_id):
                self.async_write_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _registry_changed))

    @callback
    def _entity_map(self) -> dict[str, str]:
        reg = er.async_get(self.hass)
        prefix = f"{self.coordinator.vin}_"
        out: dict[str, str] = {}
        for ent in er.async_entries_for_config_entry(reg, self.coordinator.config_entry.entry_id):
            if ent.unique_id.startswith(prefix) and not ent.disabled:
                out[ent.unique_id[len(prefix):]] = ent.entity_id
        return out

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}

        def iso(v: Any) -> Any:
            return v.isoformat() if isinstance(v, datetime) else v

        state = {k: v for k, v in data.get("state", {}).items() if not k.startswith("ola_")}
        return {
            "integration": DOMAIN,
            "vin_suffix": self.coordinator.vin[-6:],
            "vehicle_name": self.coordinator.title,
            "model": data.get("model"),
            "model_name": data.get("model_name"),
            "body": data.get("body"),
            "powertrain": data.get("powertrain"),
            "last_seen": iso(data.get("last_seen")),
            "stale": data.get("stale"),
            "commands_available": self.coordinator.ola_available,
            "sources": {
                "eu_data_act": {k: iso(v) for k, v in data.get("euda", {}).items()},
                "my_cupra": {k: iso(v) for k, v in data.get("ola", {}).items()},
            },
            "state": state,
            "entities": self._entity_map() if self.hass else {},
        }
