"""Remote climate / charging / window heating (My Cupra)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CupraConfigEntry
from .entity import CupraEntity

# key, state key, command prefix, icon, powertrains that support it
_SWITCHES = (
    ("climate", "climate_on", "climate", "mdi:air-conditioner", ("ev", "phev", None)),
    ("charging_switch", "charging", "charging", "mdi:ev-station", ("ev", "phev", None)),
    ("window_heating", "window_heating_on", "window_heating", "mdi:car-defrost-front", ("ev", "phev", None)),
)


async def async_setup_entry(hass: HomeAssistant, entry: CupraConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    if coordinator.ola is None:
        return
    pt = (coordinator.data or {}).get("powertrain")
    async_add_entities(CupraSwitch(coordinator, *s[:4]) for s in _SWITCHES if pt in s[4])


class CupraSwitch(CupraEntity, SwitchEntity):
    def __init__(self, coordinator, key: str, state_key: str, command: str, icon: str) -> None:
        super().__init__(coordinator, key)
        self._state_key = state_key
        self._command = command
        self._attr_icon = icon
        self._optimistic: bool | None = None

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.ola_available

    @property
    def is_on(self) -> bool | None:
        v = self.state_data.get(self._state_key)
        return v if isinstance(v, bool) else self._optimistic

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(f"{self._command}_on")
        self._optimistic = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(f"{self._command}_off")
        self._optimistic = False
