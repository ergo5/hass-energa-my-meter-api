"""The Energa Mobile integration v2.7.5."""
import asyncio
from datetime import timedelta, datetime
import logging
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData

from .api import EnergaAPI, EnergaAuthError, EnergaConnectionError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = EnergaAPI(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session)

    try:
        await api.async_login()
    except EnergaAuthError as err:
        raise ConfigEntryAuthFailed(err) from err
    except EnergaConnectionError as err:
        raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Rejestracja usługi
    async def import_history_service(call: ServiceCall):
        start_date_str = call.data["start_date"]
        days = call.data.get("days", 30)
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            # Uruchamiamy w tle
            hass.async_create_task(
                run_history_import(hass, api, entry.entry_id, start_date, days)
            )
        except ValueError:
            _LOGGER.error("Błędny format daty.")

    # Rejestrujemy usługę tylko jeśli jeszcze nie istnieje
    if not hass.services.has_service(DOMAIN, "fetch_history"):
        hass.services.async_register(DOMAIN, "fetch_history", import_history_service, schema=vol.Schema({
            vol.Required("start_date"): str,
            vol.Optional("days", default=30): int
        }))

    return True

async def run_history_import(hass, api, entry_id, start_date, days):
    """Import historii z opóźnieniem (Anti-Ban)."""
    _LOGGER.info(f"Energa: Rozpoczynam import historii od {start_date.date()} ({days} dni).")
    
    # ID statystyk
    stat_id_imp = f"sensor.energa_pobor_dzis"
    stat_id_exp = f"sensor.energa_produkcja_dzis"
    tz = ZoneInfo("Europe/Warsaw")

    for i in range(days):
        target_day = start_date + timedelta(days=i)
        if target_day.date() >= datetime.now().date(): break

        try:
            # === HAMULEC ===
            await asyncio.sleep(1.5)
            # ===============

            data = await api.async_get_history_hourly(target_day)
            
            stats_imp = []
            stats_exp = []
            day_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=tz)

            run_imp = 0.0
            for h, val in enumerate(data.get("import", [])):
                if val >= 0:
                    run_imp += val
                    stats_imp.append(StatisticData(
                        start=day_start+timedelta(hours=h+1), 
                        state=run_imp, 
                        sum=0.0
                    ))

            run_exp = 0.0
            for h, val in enumerate(data.get("export", [])):
                if val >= 0:
                    run_exp += val
                    stats_exp.append(StatisticData(
                        start=day_start+timedelta(hours=h+1), 
                        state=run_exp, 
                        sum=0.0
                    ))

            if stats_imp:
                async_import_statistics(hass, StatisticMetaData(
                    has_mean=False, has_sum=True, name="Energa Pobór (Dziś)", 
                    source=DOMAIN, statistic_id=stat_id_imp, unit_of_measurement="kWh"
                ), stats_imp)
            
            if stats_exp:
                async_import_statistics(hass, StatisticMetaData(
                    has_mean=False, has_sum=True, name="Energa Produkcja (Dziś)", 
                    source=DOMAIN, statistic_id=stat_id_exp, unit_of_measurement="kWh"
                ), stats_exp)

        except Exception as e:
            _LOGGER.error(f"Energa Import Error ({target_day}): {e}")
    
    _LOGGER.info(f"Energa: Zakończono import historii.")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok