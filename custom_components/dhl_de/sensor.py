"""Sensors for DHL Deutschland."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DhlConfigEntry
from .const import DOMAIN
from .coordinator import DhlCoordinator, DhlData


@dataclass(frozen=True, kw_only=True)
class DhlSensorDescription(SensorEntityDescription):
    """Describe a DHL sensor."""

    items_fn: Callable[[DhlData], list[dict[str, Any]]]
    available_fn: Callable[[DhlData], bool] = lambda _: True


SENSORS: tuple[DhlSensorDescription, ...] = (
    DhlSensorDescription(
        key="parcels_active",
        translation_key="parcels_active",
        icon="mdi:package-variant-closed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Pakete",
        items_fn=lambda d: DhlCoordinator.active(d.parcels),
    ),
    DhlSensorDescription(
        key="parcels_in_delivery",
        translation_key="parcels_in_delivery",
        icon="mdi:truck-delivery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Pakete",
        items_fn=lambda d: DhlCoordinator.in_delivery(d.parcels),
    ),
    DhlSensorDescription(
        key="parcels_all",
        translation_key="parcels_all",
        icon="mdi:package-variant",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Pakete",
        entity_registry_enabled_default=False,
        items_fn=lambda d: d.parcels,
    ),
    DhlSensorDescription(
        key="letters",
        translation_key="letters",
        icon="mdi:email-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Briefe",
        items_fn=lambda d: d.letters,
        available_fn=lambda d: d.letters_available,
    ),
)


def device_info(entry: DhlConfigEntry) -> DeviceInfo:
    """Shared device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="DHL",
        manufacturer="Deutsche Post DHL",
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: DhlConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(DhlSensor(coordinator, entry, desc) for desc in SENSORS)


class DhlSensor(CoordinatorEntity[DhlCoordinator], SensorEntity):
    """Count sensor with item list as attribute."""

    _attr_has_entity_name = True
    entity_description: DhlSensorDescription

    def __init__(self, coordinator: DhlCoordinator, entry: DhlConfigEntry, desc: DhlSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_device_info = device_info(entry)

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.available_fn(self.coordinator.data)

    @property
    def native_value(self) -> int:
        return len(self.entity_description.items_fn(self.coordinator.data))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        key = "letters" if self.entity_description.key == "letters" else "parcels"
        return {key: self.entity_description.items_fn(self.coordinator.data)}
