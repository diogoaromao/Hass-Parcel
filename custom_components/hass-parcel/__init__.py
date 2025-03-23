"""Parcel API integration for Home Assistant."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

DOMAIN = "parcel"
SCAN_INTERVAL = timedelta(minutes=15)
PARCEL_API_URL = "https://api.parcel.app/v1"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Parcel integration."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        discovery.async_load_platform(
            hass, "sensor", DOMAIN, {"api_key": config[DOMAIN][CONF_API_KEY]}, config
        )
    )

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Parcel from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    
    # Store API client for data coordinators
    hass.data.setdefault(DOMAIN, {})
    
    from .sensor import ParcelApiClient, ParcelDataUpdateCoordinator
    
    client = ParcelApiClient(api_key, hass.helpers.aiohttp_client.async_get_clientsession(hass))
    hass.data[DOMAIN][entry.entry_id] = client
    
    coordinator = ParcelDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
