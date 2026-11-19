"""Image entities for announced letters (Briefankündigung)."""

from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import DhlConfigEntry
from .api import DhlApiError
from .const import MAX_LETTER_IMAGES
from .coordinator import DhlCoordinator
from .sensor import device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: DhlConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up one image slot per letter (max MAX_LETTER_IMAGES)."""
    coordinator = entry.runtime_data
    async_add_entities(
        DhlLetterImage(hass, coordinator, entry, index) for index in range(MAX_LETTER_IMAGES)
    )


def _content_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


class DhlLetterImage(CoordinatorEntity[DhlCoordinator], ImageEntity):
    """Scan of an announced letter."""

    _attr_has_entity_name = True
    _attr_translation_key = "letter"

    def __init__(self, hass: HomeAssistant, coordinator: DhlCoordinator, entry: DhlConfigEntry, index: int) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_letter_{index + 1}"
        self._attr_translation_placeholders = {"number": str(index + 1)}
        self._attr_device_info = device_info(entry)
        self._attr_entity_registry_enabled_default = index < 3
        self._url: str | None = None
        self._image: bytes | None = None
        self._sync_url()

    def _letter(self) -> dict | None:
        letters = self.coordinator.data.letters if self.coordinator.data else []
        return letters[self._index] if self._index < len(letters) else None

    def _sync_url(self) -> None:
        letter = self._letter()
        url = letter.get("image_url") if letter else None
        if url != self._url:
            self._url = url
            self._image = None
            self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._sync_url()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        return super().available and self._url is not None

    @property
    def extra_state_attributes(self) -> dict:
        letter = self._letter() or {}
        return {k: v for k, v in letter.items() if k != "image_url"}

    async def async_image(self) -> bytes | None:
        if not self._url:
            return None
        if self._image is None:
            try:
                self._image = await self.coordinator.client.async_get_letter_image(self._url)
            except DhlApiError as err:
                _LOGGER.warning("Briefbild %s konnte nicht geladen werden: %s", self._index + 1, err)
                return None
            self._attr_content_type = _content_type(self._image)
        return self._image
