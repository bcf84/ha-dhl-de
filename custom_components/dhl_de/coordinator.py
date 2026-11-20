"""Data update coordinator for DHL Deutschland."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import html
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DhlApiError, DhlAuthError, DhlClient
from .const import (
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FORTSCHRITT_MAP,
    STATUS_DELIVERED,
    STATUS_OUT_FOR_DELIVERY,
    STATUS_READY_FOR_PICKUP,
    STATUS_UNKNOWN,
    TRACKING_LINK,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class DhlData:
    """Parsed data."""

    parcels: list[dict[str, Any]] = field(default_factory=list)
    letters: list[dict[str, Any]] = field(default_factory=list)
    letters_available: bool = False
    raw_advices: Any = None


def _fmt_time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return value


def _plain(text: str | None) -> str:
    """Strip HTML tags/entities DHL puts into status texts."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


_PICKUP_RE = re.compile(r"liegt in der (.+?) zur Abholung", re.IGNORECASE)


def parse_parcel(sendung: dict[str, Any]) -> dict[str, Any]:
    """Convert a DHL 'sendung' into a flat dict."""
    info = sendung.get("sendungsinfo", {}) or {}
    details = sendung.get("sendungsdetails", {}) or {}
    verlauf = details.get("sendungsverlauf", {}) or {}
    zustellung = details.get("zustellung", {}) or {}
    live = details.get("liveTracking") or {}

    status_text = _plain(verlauf.get("kurzStatus") or verlauf.get("status"))
    status = FORTSCHRITT_MAP.get(verlauf.get("fortschritt"), STATUS_UNKNOWN)
    lower = status_text.lower()
    if status == STATUS_UNKNOWN and "zugestellt" in lower:
        status = STATUS_DELIVERED
    pickup = _PICKUP_RE.search(status_text)
    if status != STATUS_DELIVERED and (pickup or "zur abholung bereit" in lower or "abholbereit" in lower):
        status = STATUS_READY_FOR_PICKUP

    window_from = _fmt_time(zustellung.get("zustellzeitfensterVon"))
    window_to = _fmt_time(zustellung.get("zustellzeitfensterBis"))

    parcel: dict[str, Any] = {
        "id": sendung.get("id"),
        "name": info.get("sendungsname") or "Unbekannt",
        "status": status,
        "status_text": status_text,
        "direction": info.get("sendungsrichtung"),
        "link": TRACKING_LINK.format(sendung.get("id")),
    }
    if status == STATUS_READY_FOR_PICKUP and pickup:
        parcel["pickup_location"] = pickup.group(1).strip()
    if window_from and window_to:
        parcel["delivery_window"] = f"{window_from}-{window_to}"
    if live:
        parcel["stops_left"] = live.get("countdown")
    if verlauf.get("datumAktuellerStatus"):
        parcel["last_update"] = verlauf["datumAktuellerStatus"]
    return parcel


def parse_letters(data: Any) -> list[dict[str, Any]]:
    """Find all current letter advices (dicts with image_url, not in oldAdvices)."""
    letters: list[dict[str, Any]] = []

    def walk(node: Any, skip: bool) -> None:
        if isinstance(node, dict):
            if "image_url" in node and not skip:
                letters.append({k: v for k, v in node.items() if not isinstance(v, (dict, list))})
            for key, value in node.items():
                walk(value, skip or key == "oldAdvices")
        elif isinstance(node, list):
            for item in node:
                walk(item, skip)

    walk(data, False)
    return letters


class DhlCoordinator(DataUpdateCoordinator[DhlData]):
    """Fetch data from DHL."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: DhlClient) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self.client = client

    def _persist_token(self) -> None:
        token = self.client.refresh_token
        if token and token != self.config_entry.data.get(CONF_REFRESH_TOKEN):
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, CONF_REFRESH_TOKEN: token}
            )

    async def _async_update_data(self) -> DhlData:
        result = DhlData()
        try:
            shipments = await self.client.async_get_shipments()
        except DhlAuthError as err:
            raise ConfigEntryAuthFailed("DHL Login abgelaufen, bitte neu anmelden") from err
        except DhlApiError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            self._persist_token()

        result.parcels = [parse_parcel(s) for s in shipments]

        try:
            advices = await self.client.async_get_advices()
            result.raw_advices = advices
            result.letters = parse_letters(advices)
            result.letters_available = advices is not None
        except DhlApiError as err:
            _LOGGER.info("Briefankündigung nicht verfügbar: %s", err)
            if self.data:
                result.letters = self.data.letters
                result.letters_available = self.data.letters_available
        except DhlAuthError as err:
            raise ConfigEntryAuthFailed from err
        finally:
            self._persist_token()
        return result

    @staticmethod
    def active(parcels: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Parcels not delivered yet."""
        return [p for p in parcels if p["status"] != STATUS_DELIVERED]

    @staticmethod
    def ready_for_pickup(parcels: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Parcels waiting in a Packstation / Filiale."""
        return [p for p in parcels if p["status"] == STATUS_READY_FOR_PICKUP]

    @staticmethod
    def in_delivery(parcels: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Parcels out for delivery."""
        return [p for p in parcels if p["status"] == STATUS_OUT_FOR_DELIVERY]
