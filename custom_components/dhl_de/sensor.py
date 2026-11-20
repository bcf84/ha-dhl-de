"""Sensors for DHL Deutschland."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DhlConfigEntry
from .const import (
    DOMAIN,
    STATUS_DELIVERED,
    STATUS_IN_PREPARATION,
    STATUS_IN_TRANSIT,
    STATUS_OUT_FOR_DELIVERY,
    STATUS_REGISTERED,
)
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

    # One sensor per parcel - created and removed automatically from the account data
    ent_reg = er.async_get(hass)
    known: set[str] = set()

    # remove parcel sensors left over from a previous run whose parcel is gone
    current_ids = {p["id"] for p in coordinator.data.parcels if p.get("id")}
    prefix = f"{entry.entry_id}_parcel_"
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.unique_id.startswith(prefix) and reg_entry.unique_id[len(prefix):] not in current_ids:
            ent_reg.async_remove(reg_entry.entity_id)

    @callback
    def _sync_parcels() -> None:
        ids = {p["id"] for p in coordinator.data.parcels if p.get("id")}
        new = ids - known
        if new:
            known.update(new)
            async_add_entities(DhlParcelSensor(coordinator, entry, pid) for pid in sorted(new))
        for gone in known - ids:
            known.discard(gone)
            if entity_id := ent_reg.async_get_entity_id("sensor", DOMAIN, f"{prefix}{gone}"):
                ent_reg.async_remove(entity_id)

    _sync_parcels()
    entry.async_on_unload(coordinator.async_add_listener(_sync_parcels))


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


STATUS_ICONS = {
    STATUS_REGISTERED: "mdi:package-variant",
    STATUS_IN_PREPARATION: "mdi:package-variant-closed",
    STATUS_IN_TRANSIT: "mdi:truck-fast",
    STATUS_OUT_FOR_DELIVERY: "mdi:truck-delivery",
    STATUS_DELIVERED: "mdi:package-variant-closed-check",
}


class DhlParcelSensor(CoordinatorEntity[DhlCoordinator], SensorEntity):
    """One parcel. State = DHL status text, details as attributes."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DhlCoordinator, entry: DhlConfigEntry, parcel_id: str) -> None:
        super().__init__(coordinator)
        self._parcel_id = parcel_id
        self._attr_unique_id = f"{entry.entry_id}_parcel_{parcel_id}"
        self._attr_device_info = device_info(entry)

    def _parcel(self) -> dict[str, Any] | None:
        for parcel in self.coordinator.data.parcels:
            if parcel.get("id") == self._parcel_id:
                return parcel
        return None

    @property
    def available(self) -> bool:
        return super().available and self._parcel() is not None

    @property
    def name(self) -> str:
        parcel = self._parcel() or {}
        label = parcel.get("name")
        if not label or label == "Unbekannt":
            label = self._parcel_id
        return f"Paket {label}"

    @property
    def native_value(self) -> str | None:
        parcel = self._parcel()
        if not parcel:
            return None
        return (parcel.get("status_text") or parcel.get("status") or "")[:255]

    @property
    def icon(self) -> str:
        parcel = self._parcel() or {}
        return STATUS_ICONS.get(parcel.get("status"), "mdi:package-variant")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        parcel = dict(self._parcel() or {})
        parcel.pop("name", None)
        parcel.pop("status_text", None)
        parcel["integration"] = DOMAIN
        return parcel
