"""The Energa Mobile integration v3.5.4."""
import asyncio
from datetime import timedelta, datetime
import logging
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er
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

    try: await api.async_login()
    except EnergaAuthError as err: raise ConfigEntryAuthFailed(err) from err
    except EnergaConnectionError as err: raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def import_history_service(call: ServiceCall):
        start_date_str = call.data["start_date"]
        days = call.data.get("days", 30)
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            meters = await api.async_get_data()
            for meter in meters:
                hass.async_create_task(run_history_import(hass, api, meter["meter_point_id"], start_date, days))
        except ValueError: _LOGGER.error("Błędny format daty.")

    if not hass.services.has_service(DOMAIN, "fetch_history"):
        hass.services.async_register(DOMAIN, "fetch_history", import_history_service, schema=vol.Schema({
            vol.Required("start_date"): str,
            vol.Optional("days", default=30): int
        }))
    return True

async def run_history_import(hass, api, meter_id, start_date, days):
    _LOGGER.info(f"Energa [{meter_id}]: Start importu v3.5.4 (Final Logic Fix).")
    ent_reg = er.async_get(hass)
    
    # Celujemy w sensory v2 (te czyste)
    uid_imp = f"energa_import_total_{meter_id}"
    uid_exp = f"energa_export_total_{meter_id}"
    
    entity_id_imp = ent_reg.async_get_entity_id("sensor", DOMAIN, uid_imp)
    entity_id_exp = ent_reg.async_get_entity_id("sensor", DOMAIN, uid_exp)
    
    if not entity_id_imp: 
        entity_id_imp = f"sensor.energa_import_total_{meter_id}"
    if not entity_id_exp: 
        entity_id_exp = f"sensor.energa_export_total_{meter_id}"

    tz = ZoneInfo("Europe/Warsaw")

    current_sum_imp = 0.0
    current_sum_exp = 0.0

    for i in range(days):
        target_day = start_date + timedelta(days=i)
        if target_day.date() >= datetime.now().date(): break
        try:
            await asyncio.sleep(1.0)
            data = await api.async_get_history_hourly(meter_id, target_day)
            
            stats_imp = []
            stats_exp = []
            day_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=tz)

            # Start dnia: state = sum (z poprzedniego dnia)
            stats_imp.append(StatisticData(start=day_start, state=current_sum_imp, sum=current_sum_imp))
            stats_exp.append(StatisticData(start=day_start, state=current_sum_exp, sum=current_sum_exp))
            
            # Agregacja godzinowa
            for h, val in enumerate(data.get("import", [])):
                if val >= 0:
                    current_sum_imp += val
                    dt_hour = day_start + timedelta(hours=h+1)
                    stats_imp.append(StatisticData(start=dt_hour, state=current_sum_imp, sum=current_sum_imp))
            
            for h, val in enumerate(data.get("export", [])):
                if val >= 0:
                    current_sum_exp += val
                    dt_hour = day_start + timedelta(hours=h+1)
                    stats_exp.append(StatisticData(start=dt_hour, state=current_sum_exp, sum=current_sum_exp))

            # ZAPIS DO BAZY
            if stats_imp:
                async_import_statistics(hass, StatisticMetaData(
                    has_mean=False, has_sum=True, name=None, source='recorder', statistic_id=entity_id_imp, 
                    unit_of_measurement="kWh", unit_class="energy"
                ), stats_imp)
                
                # FIX: Aktualizujemy stan sensora LIVE TYLKO RAZ NA KONIEC DNIA.
                hass.states.async_set(
                    entity_id_imp, 
                    current_sum_imp, 
                    {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"}
                )

            if stats_exp:
                async_import_statistics(hass, StatisticMetaData(
                    has_mean=False, has_sum=True, name=None, source='recorder', statistic_id=entity_id_exp, 
                    unit_of_measurement="kWh", unit_class="energy"
                ), stats_exp)

                # FIX: Aktualizujemy stan sensora LIVE TYLKO RAZ NA KONIEC DNIA.
                hass.states.async_set(
                    entity_id_exp, 
                    current_sum_exp, 
                    {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"}
                )
                
        except Exception as e: _LOGGER.error(f"Energa Import Error: {e}")
    _LOGGER.info(f"Energa [{meter_id}]: Zakończono import.")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok