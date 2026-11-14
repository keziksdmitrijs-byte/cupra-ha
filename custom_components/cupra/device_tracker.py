"""GPS position (only from the My Cupra connection – the EU Data Act has no location)."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CupraConfigEntry
from .entity import CupraEntity, add_dynamic


async def async_setup_entry(hass: HomeAssistant, entry: CupraConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data

    def factory(created: set[str]):
        state = (coordinator.data or {}).get("state", {})
        if "position" in created or state.get("latitude") is None:
            return []
        return [CupraTracker(coordinator)]

    entry.async_on_unload(add_dynamic(hass, coordinator, async_add_entities, factory))


class CupraTracker(CupraEntity, TrackerEntity):
    _attr_icon = "mdi:car"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "position")

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self.state_data.get("latitude")

    @property
    def longitude(self) -> float | None:
        return self.state_data.get("longitude")
