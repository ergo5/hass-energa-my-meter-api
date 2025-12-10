from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from .const import DOMAIN

STEP_USER = vol.Schema({
    vol.Required("username"): str,
    vol.Required("password"): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, info=None):
        if info is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER)

        return self.async_create_entry(title="Energa Meter", data=info)
