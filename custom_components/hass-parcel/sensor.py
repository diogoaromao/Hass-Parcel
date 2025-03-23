"""Sensor platform for Parcel integration."""
import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import DOMAIN, SCAN_INTERVAL, PARCEL_API_URL

_LOGGER = logging.getLogger(__name__)

class ParcelApiClient:
    """API client for Parcel."""

    def __init__(self, api_key, session):
        """Initialize the API client."""
        self.api_key = api_key
        self.session = session
        
    async def validate_api_key(self):
        """Validate the API key."""
        try:
            # Try to fetch shipments to validate
            await self.get_shipments()
            return True
        except Exception as err:
            _LOGGER.error("Error validating Parcel API key: %s", err)
            return False
    
    async def get_shipments(self):
        """Get shipments from Parcel API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with self.session.get(
            f"{PARCEL_API_URL}/shipments", headers=headers
        ) as resp:
            if resp.status != 200:
                raise Exception(f"Error fetching shipments: {resp.status}")
            
            data = await resp.json()
            return data.get("shipments", [])

class ParcelDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Parcel data."""

    def __init__(self, hass, client):
        """Initialize data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        
    async def _async_update_data(self):
        """Update data via API."""
        try:
            return await self.client.get_shipments()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Parcel API: {err}")

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the Parcel sensor platform."""
    if discovery_info is None:
        return
    
    api_key = discovery_info["api_key"]
    client = ParcelApiClient(api_key, hass.helpers.aiohttp_client.async_get_clientsession(hass))
    
    coordinator = ParcelDataUpdateCoordinator(hass, client)
    await coordinator.async_refresh()
    
    async_add_entities(
        ParcelDeliverySensor(coordinator, idx, shipment)
        for idx, shipment in enumerate(coordinator.data)
    )

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Parcel sensors from a config entry."""
    client = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = ParcelDataUpdateCoordinator(hass, client)
    await coordinator.async_refresh()
    
    if not coordinator.data:
        return
    
    entities = []
    for idx, shipment in enumerate(coordinator.data):
        entities.append(ParcelDeliverySensor(coordinator, idx, shipment))
    
    async_add_entities(entities)

class ParcelDeliverySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Parcel delivery sensor."""

    def __init__(self, coordinator, idx, shipment):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.idx = idx
        self.shipment = shipment
        self._attr_unique_id = f"parcel_delivery_{shipment.get('id', idx)}"
        self._attr_name = f"Parcel Delivery {shipment.get('name', f'#{idx+1}')}"
        self._attr_icon = "mdi:package-variant"
        self._attr_device_class = SensorDeviceClass.ENUM
        self.update_attributes()
    
    def update_attributes(self):
        """Update attributes based on current data."""
        shipment = self.coordinator.data[self.idx] if self.idx < len(self.coordinator.data) else {}
        
        self._attr_native_value = shipment.get("status", "unknown")
        
        # Prepare attributes for the card
        self._attr_extra_state_attributes = {
            "name": shipment.get("name", "Unknown"),
            "carrier": shipment.get("carrier", {}).get("name", "Unknown"),
            "tracking_number": shipment.get("tracking_number", "Unknown"),
            "status": shipment.get("status", "Unknown"),
            "last_update": shipment.get("last_update", "Unknown"),
            "estimated_delivery": shipment.get("estimated_delivery", "Unknown"),
            "from_location": shipment.get("from_location", "Unknown"),
            "to_location": shipment.get("to_location", "Unknown"),
            "shipment_id": shipment.get("id", "Unknown"),
        }
        
        # Custom status color for Lovelace card
        status = shipment.get("status", "").lower()
        if "delivered" in status:
            self._attr_extra_state_attributes["status_color"] = "green"
        elif "transit" in status:
            self._attr_extra_state_attributes["status_color"] = "blue"
        elif "exception" in status or "failed" in status:
            self._attr_extra_state_attributes["status_color"] = "red"
        elif "pending" in status or "pre-transit" in status:
            self._attr_extra_state_attributes["status_color"] = "orange"
        else:
            self._attr_extra_state_attributes["status_color"] = "grey"
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.idx < len(self.coordinator.data)
    
    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()
        if self.idx < len(self.coordinator.data):
            self.shipment = self.coordinator.data[self.idx]
            self.update_attributes()
