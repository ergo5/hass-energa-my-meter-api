"""The Energa Mobile integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import EnergaAPI
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN
import logging

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    
    api = EnergaAPI(
        entry.data[CONF_USERNAME], 
        entry.data[CONF_PASSWORD],
        entry.data[CONF_TOKEN],
        session
    )

    try: await api.async_login() 
    except: pass

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok