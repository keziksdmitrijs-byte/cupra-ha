"""Central locking (My Cupra, needs S-PIN)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CupraConfigEntry
from .entity import CupraEntity


async def async_setup_entry(hass: HomeAssistant, entry: CupraConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    if coordinator.ola is not None:
        async_add_entities([CupraLock(coordinator)])


class CupraLock(CupraEntity, LockEntity):
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "door_lock")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.ola_available

    @property
    def is_locked(self) -> bool | None:
        return self.state_data.get("locked")

    async def async_lock(self, **kwargs: Any) -> None:
        await self.coordinator.async_command("lock")

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.coordinator.async_command("unlock")
