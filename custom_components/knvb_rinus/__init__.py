from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import RinusClient, RinusDataError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = RinusClient(hass, {**entry.data, **entry.options})

    async def async_update_data():
        try:
            return await client.async_fetch_all()
        except RinusDataError as err:
            _LOGGER.error("KNVB Rinus update mislukt: %s", err)
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Onverwachte fout bij ophalen van KNVB Rinus data")
            raise UpdateFailed("Onverwachte fout bij ophalen van KNVB Rinus data") from err

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(
            seconds=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        ),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _options_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
        if not data:
            return
        new_interval = config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        data["coordinator"].update_interval = timedelta(seconds=new_interval)
        _LOGGER.debug("KNVB Rinus polling interval aangepast naar %s seconden", new_interval)

    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if data and data.get("client"):
            await data["client"].async_close()
    return unloaded
