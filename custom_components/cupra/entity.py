"""Shared entity base."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS, VERSION
from .coordinator import CupraCoordinator


class CupraEntity(CoordinatorEntity[CupraCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: CupraCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{coordinator.vin}_{key}"
        self._attr_translation_key = key
        model = (coordinator.data or {}).get("model")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.vin)},
            name=coordinator.title,
            manufacturer="CUPRA",
            model=MODELS.get(model or "", {}).get("name"),
            serial_number=coordinator.vin,
            sw_version=f"integration {VERSION}",
        )

    @property
    def state_data(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("state", {})


def add_dynamic(
    hass: HomeAssistant,
    coordinator: CupraCoordinator,
    async_add_entities: AddEntitiesCallback,
    factory: Callable[[set[str]], Iterable[Entity]],
) -> Callable[[], None]:
    """Add entities now, and again whenever new signals show up in later snapshots.

    ``factory`` receives the set of keys already created and returns only new entities.
    """
    created: set[str] = set()

    @callback
    def _check() -> None:
        new = [e for e in factory(created)]
        for e in new:
            created.add(e.key)  # type: ignore[attr-defined]
        if new:
            async_add_entities(new)

    _check()
    return coordinator.async_add_listener(_check)
