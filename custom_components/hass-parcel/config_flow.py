"""Config flow for Parcel integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY

from . import DOMAIN
from .sensor import ParcelApiClient

_LOGGER = logging.getLogger(__name__)

class ParcelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Parcel."""

    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            
            # Validate the API key
            client = ParcelApiClient(
                api_key, 
                self.hass.helpers.aiohttp_client.async_get_clientsession()
            )
            
            try:
                valid = await client.validate_api_key()
                if valid:
                    return self.async_create_entry(
                        title="Parcel Deliveries",
                        data={CONF_API_KEY: api_key},
                    )
                else:
                    errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
