"""DHL Deutschland – Pakete und Briefankündigung für Home Assistant."""

from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import DhlClient
from .const import CONF_REFRESH_TOKEN
from .coordinator import DhlCoordinator

PLATFORMS = [Platform.SENSOR, Platform.IMAGE]

type DhlConfigEntry = ConfigEntry[DhlCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DhlConfigEntry) -> bool:
    """Set up DHL from a config entry."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    client = DhlClient(session, entry.data[CONF_REFRESH_TOKEN])
    coordinator = DhlCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    options_at_setup = dict(entry.options)

    async def _async_reload(hass: HomeAssistant, entry: DhlConfigEntry) -> None:
        """Reload only when options change (not on token updates)."""
        if dict(entry.options) != options_at_setup:
            await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DhlConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
