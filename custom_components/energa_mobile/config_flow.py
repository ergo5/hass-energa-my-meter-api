import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class EnergaFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            schema = vol.Schema({
                vol.Required("username"): str,
                vol.Required("password"): str
            })
            return self.async_show_form(step_id="user", data_schema=schema)

        user_input["token"] = "aabbccddeeff00112233445566778899"

        return self.async_create_entry(
            title="Energa Meter",
            data=user_input
        )
