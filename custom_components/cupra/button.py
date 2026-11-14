"""Buttons: refresh (always), flash / honk / wake-up (My Cupra)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CupraConfigEntry
from .entity import CupraEntity

_OLA_BUTTONS = (
    ("flash", "mdi:car-light-high"),
    ("honk_flash", "mdi:bullhorn"),
    ("wakeup", "mdi:sleep-off"),
)


async def async_setup_entry(hass: HomeAssistant, entry: CupraConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = [CupraRefreshButton(coordinator)]
    if coordinator.ola is not None:
        entities += [CupraCommandButton(coordinator, key, icon) for key, icon in _OLA_BUTTONS]
    async_add_entities(entities)


class CupraRefreshButton(CupraEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_force_refresh()


class CupraCommandButton(CupraEntity, ButtonEntity):
    def __init__(self, coordinator, key: str, icon: str) -> None:
        super().__init__(coordinator, key)
        self._attr_icon = icon

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.ola_available

    async def async_press(self) -> None:
        await self.coordinator.async_command(self.key)
