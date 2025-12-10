"""Config flow for Energa Mobile integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import EnergaAPI, EnergaAuthError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

class EnergaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = EnergaAPI(
                user_input[CONF_USERNAME], 
                user_input[CONF_PASSWORD], 
                session
            )
            try:
                await api.async_login()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], 
                    data=user_input
                )
            except EnergaAuthError: errors["base"] = "invalid_auth"
            except Exception: errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str
            }),
            errors=errors,
        )