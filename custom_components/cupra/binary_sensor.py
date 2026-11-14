"""Binary sensors: doors, windows, lock, charging, plug…"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass as BC,
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CupraConfigEntry
from .coordinator import CupraCoordinator
from .entity import CupraEntity, add_dynamic


@dataclass(frozen=True, kw_only=True)
class CupraBinaryDescription(BinarySensorEntityDescription):
    invert: bool = False


def _b(key: str, dc: BC | None = None, **kw) -> CupraBinaryDescription:
    return CupraBinaryDescription(key=key, translation_key=key, device_class=dc, **kw)


BINARIES: tuple[CupraBinaryDescription, ...] = (
    # LOCK device class: on = unlocked
    _b("locked", BC.LOCK, invert=True),
    _b("doors_open", BC.DOOR),
    _b("windows_open", BC.WINDOW),
    _b("door_fl", BC.DOOR),
    _b("door_fr", BC.DOOR),
    _b("door_rl", BC.DOOR),
    _b("door_rr", BC.DOOR),
    _b("trunk", BC.DOOR, icon="mdi:car-back"),
    _b("hood", BC.DOOR, icon="mdi:car"),
    _b("window_fl", BC.WINDOW),
    _b("window_fr", BC.WINDOW),
    _b("window_rl", BC.WINDOW),
    _b("window_rr", BC.WINDOW),
    _b("sunroof", BC.WINDOW, icon="mdi:car-select"),
    _b("charging", BC.BATTERY_CHARGING),
    _b("plug_connected", BC.PLUG),
    _b("climate_on", BC.RUNNING, icon="mdi:air-conditioner"),
    _b("parking_brake", None, icon="mdi:car-brake-parking"),
    _b("parking_lights", BC.LIGHT),
    _b("moving", BC.MOVING),
)


async def async_setup_entry(hass: HomeAssistant, entry: CupraConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([CupraStaleSensor(coordinator)])

    def factory(created: set[str]):
        state = (coordinator.data or {}).get("state", {})
        return [CupraBinary(coordinator, d) for d in BINARIES if d.key not in created and isinstance(state.get(d.key), bool)]

    entry.async_on_unload(add_dynamic(hass, coordinator, async_add_entities, factory))


class CupraBinary(CupraEntity, BinarySensorEntity):
    entity_description: CupraBinaryDescription

    def __init__(self, coordinator: CupraCoordinator, description: CupraBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        v = self.state_data.get(self.key)
        if not isinstance(v, bool):
            return None
        return not v if self.entity_description.invert else v


class CupraStaleSensor(CupraEntity, BinarySensorEntity):
    """On when no fresh data arrived for 12 h (car asleep or portal problem)."""

    _attr_device_class = BC.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CupraCoordinator) -> None:
        super().__init__(coordinator, "stale")

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("stale"))
