"""Config flow for Energa Mobile integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import EnergaAPI, EnergaAuthError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

class EnergaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Obsługa pierwszej instalacji."""
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
                
                # Sprawdzamy czy takie konto już istnieje
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()

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

    async def async_step_reauth(self, entry_data):
        """Wywoływane, gdy HA wykryje błąd uwierzytelniania."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Formularz zmiany hasła."""
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            # Używamy starego loginu, nowe hasło
            username = self.reauth_entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            api = EnergaAPI(username, password, session)

            try:
                await api.async_login()
                
                # Aktualizacja hasła w istniejącej konfiguracji
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password
                    }
                )
                
                # Przeładowanie integracji
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            except EnergaAuthError: errors["base"] = "invalid_auth"
            except Exception: errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_PASSWORD): str
            }),
            description_placeholders={
                "username": self.reauth_entry.data[CONF_USERNAME]
            },
            errors=errors,
        )