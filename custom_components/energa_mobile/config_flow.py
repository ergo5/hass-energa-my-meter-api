"""Config flow for Energa Mobile integration v2.8.7."""
import logging  # <--- Tego brakowało!
import voluptuous as vol
from datetime import datetime
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from .api import EnergaAPI, EnergaAuthError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

class EnergaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EnergaOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = EnergaAPI(user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session)
            try:
                await api.async_login()
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
            except EnergaAuthError: errors["base"] = "invalid_auth"
            except Exception: errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}), errors=errors)

    async def async_step_reauth(self, entry_data):
        self.reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            u = self.reauth_entry.data[CONF_USERNAME]
            p = user_input[CONF_PASSWORD]
            api = EnergaAPI(u, p, session)
            try:
                await api.async_login()
                self.hass.config_entries.async_update_entry(self.reauth_entry, data={CONF_USERNAME: u, CONF_PASSWORD: p})
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except EnergaAuthError: errors["base"] = "invalid_auth"
            except Exception: errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}), description_placeholders={"username": self.reauth_entry.data[CONF_USERNAME]}, errors=errors)

class EnergaOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["credentials", "history"])

    async def async_step_credentials(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = EnergaAPI(user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session)
            try:
                await api.async_login()
                self.hass.config_entries.async_update_entry(self._config_entry, data=user_input)
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            except EnergaAuthError: errors["base"] = "invalid_auth"
            except Exception: errors["base"] = "cannot_connect"
        current_user = self._config_entry.data.get(CONF_USERNAME)
        return self.async_show_form(step_id="credentials", data_schema=vol.Schema({vol.Required(CONF_USERNAME, default=current_user): str, vol.Required(CONF_PASSWORD): str}), errors=errors)

    async def async_step_history(self, user_input=None):
        from .__init__ import run_history_import
        api = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        if not api: return self.async_abort(reason="integration_not_ready")

        contract_str = "Nieznana"
        default_date = None
        if api._meter_data and api._meter_data.get("contract_date"):
            contract_str = str(api._meter_data["contract_date"])
            default_date = str(api._meter_data["contract_date"])
        
        if user_input is not None:
            start_date = datetime.strptime(user_input["start_date"], "%Y-%m-%d")
            diff = (datetime.now() - start_date).days
            if diff < 1: diff = 1
            self.hass.async_create_task(run_history_import(self.hass, api, self._config_entry.entry_id, start_date, diff))
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="history", data_schema=vol.Schema({vol.Required("start_date", default=default_date): selector.DateSelector()}), description_placeholders={"contract_date": contract_str})