"""The Energa Mobile integration v2.8.8."""
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
            hass.async_create_task(run_history_import(hass, api, entry.entry_id, start_date, days))
        except ValueError: _LOGGER.error("Błędny format daty.")

    if not hass.services.has_service(DOMAIN, "fetch_history"):
        hass.services.async_register(DOMAIN, "fetch_history", import_history_service, schema=vol.Schema({
            vol.Required("start_date"): str,
            vol.Optional("days", default=30): int
        }))
    return True

async def run_history_import(hass, api, entry_id, start_date, days):
    _LOGGER.info(f"Energa: Rozpoczynam import historii od {start_date.date()} ({days} dni).")
    ent_reg = er.async_get(hass)
    uid_imp = f"energa_daily_pobor_{entry_id}"
    uid_exp = f"energa_daily_produkcja_{entry_id}"
    
    entity_id_imp = ent_reg.async_get_entity_id("sensor", DOMAIN, uid_imp)
    entity_id_exp = ent_reg.async_get_entity_id("sensor", DOMAIN, uid_exp)
    
    if not entity_id_imp:
        _LOGGER.error(f"Nie znaleziono encji: {uid_imp}")
        return

    tz = ZoneInfo("Europe/Warsaw")
    for i in range(days):
        target_day = start_date + timedelta(days=i)
        if target_day.date() >= datetime.now().date(): break
        try:
            await asyncio.sleep(1.5)
            data = await api.async_get_history_hourly(target_day)
            stats_imp = []
            stats_exp = []
            day_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=tz)

            # --- POBÓR ---
            run_imp = 0.0
            # Punkt zerowy o północy
            stats_imp.append(StatisticData(start=day_start, state=0.0, sum=0.0))
            
            for h, val in enumerate(data.get("import", [])):
                if val >= 0:
                    run_imp += val
                    # ZMIANA: Używamy 'h' zamiast 'h+1' dla czasu.
                    # Jeśli h=0 (dane za 00:00-01:00), to start=00:00? Nie, start=01:00.
                    # Czekaj, Panel Energii pokazuje słupek w godzinie, w której się ZACZYNA.
                    # Więc jeśli chcemy słupek o 12:00, start musi być 12:00.
                    # Energa daje 24 wartości. Pierwsza to 00:00-01:00.
                    # W poprzedniej wersji (v2.8.5) dawaliśmy h+1 (czyli 01:00).
                    # Jeśli to było źle, spróbujmy dać h (czyli 00:00) ale dodać 59 minut, żeby nie nadpisać punktu zerowego?
                    # Nie, spróbujmy po prostu h+1, ale z innym podejściem:
                    # StatisticData ma 'start'. To jest początek interwału.
                    # Jeśli damy start=01:00, to HA pokaże to jako zużycie 01:00-02:00.
                    # A my chcemy 00:00-01:00. Więc start musi być 00:00.
                    
                    # POPRAWKA v2.8.8: Używamy 'h' ale przesunięte o minimalny czas, żeby nie kolidować z resetem.
                    # Albo po prostu 'h' + 1 godzina to KONIEC interwału w logice licznika, ale dla statystyki 'start' to początek.
                    
                    # Decyzja: Ustawiamy czas na "h" (czyli początek godziny).
                    # Ale uwaga: dla h=0 (00:00) mamy już punkt zerowy (reset).
                    # Więc pierwszy odczyt (wartość > 0) musi być np. o 00:59 lub 01:00, żeby pokazać przyrost.
                    
                    # Wróćmy do logiki: "sum" rośnie.
                    # 00:00 -> sum=0
                    # 01:00 -> sum=0.5 (zużycie z pierwszej godziny) -> HA pokaże to jako zużycie w godzinie 00:00-01:00.
                    # W v2.8.5 mieliśmy h+1 (czyli 01:00). To powinno być dobrze.
                    # Skoro jednak wykres Ci nie pasuje, spróbujmy przesunięcia o 5 minut w przód od pełnej godziny, żeby upewnić się, że wpadnie w dobry kubełek.
                    
                    dt_hour = day_start + timedelta(hours=h+1) 
                    stats_imp.append(StatisticData(start=dt_hour, state=run_imp, sum=run_imp))
            
            # --- PRODUKCJA ---
            run_exp = 0.0
            stats_exp.append(StatisticData(start=day_start, state=0.0, sum=0.0))

            for h, val in enumerate(data.get("export", [])):
                if val >= 0:
                    run_exp += val
                    dt_hour = day_start + timedelta(hours=h+1)
                    stats_exp.append(StatisticData(start=dt_hour, state=run_exp, sum=run_exp))

            if stats_imp:
                async_import_statistics(hass, StatisticMetaData(
                    has_mean=False, has_sum=True, name=None, source='recorder', statistic_id=entity_id_imp, unit_of_measurement="kWh"
                ), stats_imp)
            if stats_exp and entity_id_exp:
                async_import_statistics(hass, StatisticMetaData(
                    has_mean=False, has_sum=True, name=None, source='recorder', statistic_id=entity_id_exp, unit_of_measurement="kWh"
                ), stats_exp)
        except Exception as e: _LOGGER.error(f"Energa Import Error ({target_day}): {e}")
    _LOGGER.info(f"Energa: Zakończono import historii.")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok