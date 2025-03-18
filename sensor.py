"""
Parcel API integration for Home Assistant.
For more information about this integration, please visit:
https://github.com/diogoaromao/hass-parcel
"""
import logging
import asyncio
import aiohttp
from datetime import timedelta
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

# Base component constants
DOMAIN = "parcel"
PARCEL_API_URL = "https://api.parcel.app/v1"
DEFAULT_NAME = "Parcel"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

# Configuration schema
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.time_period,
    }
)

# Service call validation schema
SERVICE_REFRESH_SCHEMA = vol.Schema({})

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the Parcel sensor platform."""
    api_key = config[CONF_API_KEY]
    name = config[CONF_NAME]
    scan_interval = config[CONF_SCAN_INTERVAL]

    # Create data coordinator
    coordinator = ParcelDataCoordinator(hass, api_key, scan_interval)
    
    # Fetch initial data
    await coordinator.async_refresh()

    # Create service for manual refresh
    async def async_refresh_parcels(call):
        """Refresh Parcel data."""
        await coordinator.async_refresh()

    hass.services.async_register(
        DOMAIN, "refresh", async_refresh_parcels, schema=SERVICE_REFRESH_SCHEMA
    )

    # Add entities
    entities = []
    for parcel_id, parcel_data in coordinator.data.items():
        entities.append(ParcelSensor(coordinator, parcel_id, name))
    
    async_add_entities(entities, True)

class ParcelDataCoordinator:
    """Class to manage fetching Parcel data."""

    def __init__(self, hass, api_key, update_interval):
        """Initialize."""
        self.hass = hass
        self.api_key = api_key
        self.update_interval = update_interval
        self.data = {}
        self._request_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @Throttle(DEFAULT_SCAN_INTERVAL)
    async def async_refresh(self):
        """Fetch data from Parcel API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{PARCEL_API_URL}/shipments",
                    headers=self._request_headers,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.data = {
                            str(shipment["id"]): shipment for shipment in data.get("shipments", [])
                        }
                        _LOGGER.debug("Parcel data refreshed: %s shipments", len(self.data))
                    else:
                        _LOGGER.error(
                            "Error fetching Parcel data: %s - %s",
                            resp.status,
                            await resp.text(),
                        )
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            _LOGGER.error("Error fetching Parcel data: %s", error)

class ParcelSensor(SensorEntity):
    """Implementation of a Parcel sensor."""

    def __init__(self, coordinator, parcel_id, name_prefix):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.parcel_id = parcel_id
        self._name = f"{name_prefix} {self.parcel_data.get('carrier', '')} {self.parcel_data.get('tracking_number', '')}"
        self._unique_id = f"parcel_{parcel_id}"

    @property
    def parcel_data(self):
        """Return the parcel data."""
        return self.coordinator.data.get(self.parcel_id, {})

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.parcel_data.get("status", "unknown")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        
        if self.parcel_data:
            attrs["carrier"] = self.parcel_data.get("carrier")
            attrs["tracking_number"] = self.parcel_data.get("tracking_number")
            attrs["status"] = self.parcel_data.get("status")
            attrs["status_description"] = self.parcel_data.get("status_description")
            attrs["estimated_delivery"] = self.parcel_data.get("estimated_delivery")
            attrs["last_update"] = self.parcel_data.get("last_update")
            
            # Add location information if available
            if "location" in self.parcel_data:
                attrs["location"] = self.parcel_data.get("location")
            
            # Add tracking history if available
            if "tracking_history" in self.parcel_data:
                attrs["tracking_history"] = self.parcel_data.get("tracking_history")

        return attrs

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        status = self.parcel_data.get("status", "").lower()
        
        if status == "delivered":
            return "mdi:package-variant-closed-check"
        elif status == "in_transit":
            return "mdi:truck-delivery"
        elif status == "out_for_delivery":
            return "mdi:truck-fast"
        elif status == "exception" or status == "failure":
            return "mdi:alert-circle"
        else:
            return "mdi:package-variant-closed"

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_refresh()
