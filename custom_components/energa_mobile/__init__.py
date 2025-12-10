"""The Energa Mobile integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from .api import EnergaAPI, EnergaAuthError, EnergaConnectionError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    
    api = EnergaAPI(
        entry.data[CONF_USERNAME], 
        entry.data[CONF_PASSWORD],
        session
    )

    try:
        # Próba logowania przy starcie
        await api.async_login()
    except EnergaAuthError as err:
        # To uruchomi proces "Reconfigure" w HA
        raise ConfigEntryAuthFailed(f"Błędne dane logowania: {err}") from err
    except EnergaConnectionError as err:
        # To sprawi, że HA spróbuje ponownie później (np. brak internetu)
        raise ConfigEntryNotReady(f"Błąd połączenia z API: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok