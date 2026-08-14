"""KNVB Rinus Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import RinusAuthError
from .const import DOMAIN
from .coordinator import RinusCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KNVB Rinus from a config entry."""
    coordinator = RinusCoordinator(
        hass,
        async_get_clientsession(hass),
        entry,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except RinusAuthError as err:
        raise ConfigEntryAuthFailed("Rinus session has expired") from err

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload KNVB Rinus."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
