"""The Energa Mobile integration v3.6.0-beta.10."""
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
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData, StatisticType
from homeassistant.components import persistent_notification

# FIX: Dodajemy obsługę błędu wygaśnięcia tokena
from .api import EnergaAPI, EnergaAuthError, EnergaConnectionError, EnergaTokenExpiredError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = EnergaAPI(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session)

    try: await api.async_login()
    except EnergaAuthError as err: raise ConfigEntryAuthFailed(err) from err
    # FIX: Obsługa błędu wygaśnięcia tokena, by nie powodował ConfigEntryNotReady
    except EnergaTokenExpiredError as err:
        _LOGGER.warning("Token wygasł podczas startu. Próbuję ponownego logowania.")
        try:
            await api.async_login()
        except EnergaAuthError as err: raise ConfigEntryAuthFailed(err) from err
        except EnergaConnectionError as err: raise ConfigEntryNotReady(err) from err
    
    except EnergaConnectionError as err: raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ... reszta kodu async_setup_entry (serwis importu historii) (bez zmian) ...
    async def import_history_service(call: ServiceCall) -> None:
        start_date_str = call.data["start_date"]
        days = call.data.get("days", 30)
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            meters = await api.async_get_data()
            
            for meter in meters:
                meter_point = meter
                # FIX v3.5.24: Explicitly handle string IDs if API quirks return them mixed
                if isinstance(meter, str): 
                    # Try to find corresponding dict in fresh fetch
                    ref_data = await api.async_get_data(force_refresh=True)
                    meter_point = next((m for m in ref_data if str(m["meter_point_id"]) == str(meter)), None)
                
                if meter_point and isinstance(meter_point, dict):
                    hass.async_create_task(run_history_import(hass, api, meter_point, start_date, days))
                else:
                    _LOGGER.error(f"Energa Import: Could not resolve meter data for {meter}. Skipping.")
                    
        except ValueError: _LOGGER.error("Błędny format daty.")

        except ValueError: _LOGGER.error("Błędny format daty.")

    # Always register service to ensure latest code is used (v3.5.25)
    hass.services.async_register(DOMAIN, "fetch_history", import_history_service, schema=vol.Schema({
        vol.Required("start_date"): str,
        vol.Optional("days", default=30): int
    }))
    return True

async def run_history_import(hass: HomeAssistant, api: EnergaAPI, meter_data: dict, start_date: datetime, days: int) -> None:
    # PARANOID FIX v3.5.25: Even with upstream checks, if this function gets a string, FIX IT.
    if isinstance(meter_data, str):
        _LOGGER.warning(f"Energa Import: Internal function received STRING '{meter_data}'. Activating fail-safe fetch.")
        try:
            # v3.6.0-beta.1: Force Refresh to ensure we don't get stale/zero cache
            ref_data = await api.async_get_data(force_refresh=True)
            found = next((m for m in ref_data if str(m["meter_point_id"]) == str(meter_data)), None)
            if found: meter_data = found
            else:
                _LOGGER.error(f"Energa Import: Fail-safe could not resolve ID {meter_data}. Aborting.")
                return
        except Exception as e:
            _LOGGER.error(f"Energa Import: Fail-safe crash: {e}")
            return

    meter_id = meter_data["meter_point_id"]
    serial = meter_data.get("meter_serial", meter_id)
    
    _LOGGER.info(f"Energa [{serial}]: Start importu v3.6.0-beta.1 (Fresh-Anchor).")
    
    persistent_notification.async_create(
        hass,
        f"Rozpoczęto pobieranie historii dla licznika {serial} (zakres: {days} dni).",
        title="Energa Mobile: Import Historii",
        notification_id=f"energa_import_start_{meter_id}"
    )

    try:
        ent_reg = er.async_get(hass)
        
        # Target entities (nuclear v3 IDs)
        uid_imp_total = f"energa_import_total_{meter_id}_v3"
        uid_exp_total = f"energa_export_total_{meter_id}_v3"
        
        uid_imp_daily = f"energa_daily_pobor_{meter_id}" # Daily sensors don't need v3 rotation usually, but verifying
        uid_exp_daily = f"energa_daily_produkcja_{meter_id}"
        
        def get_entity_id(uid, default_guess):
            eid = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
            return eid if eid else default_guess
        
        entity_id_imp = get_entity_id(uid_imp_total, f"sensor.energa_import_total_{meter_id}_v3")
        entity_id_exp = get_entity_id(uid_exp_total, f"sensor.energa_export_total_{meter_id}_v3")
        
        entity_id_imp_daily = get_entity_id(uid_imp_daily, f"sensor.energa_pobor_dzis_{meter_id}")
        entity_id_exp_daily = get_entity_id(uid_exp_daily, f"sensor.energa_produkcja_dzis_{meter_id}")

        tz = ZoneInfo("Europe/Warsaw")
        
        anchor_imp = float(meter_data.get("total_plus", 0.0))
        anchor_exp = float(meter_data.get("total_minus", 0.0))

        # Check for zero anchor (v3.5.22 logic preserved)
        if anchor_imp == 0 and anchor_exp == 0:
             # Try refresh one last time (Force Refresh - v3.6.0-beta.1)
             try:
                 fresh = await api.async_get_data(force_refresh=True)
                 target = next((m for m in fresh if str(m["meter_point_id"]) == str(meter_id)), None)
                 if target:
                     anchor_imp = float(target.get("total_plus", 0.0))
                     anchor_exp = float(target.get("total_minus", 0.0))
             except: pass
        
        # DIAGNOSTIC LOG (v3.6.0-beta.1)
        _LOGGER.info(f"Energa Import Anchors: IMP={anchor_imp}, EXP={anchor_exp}")

        all_imp_data = [] 
        all_exp_data = []

        for i in range(days):
            target_day = start_date + timedelta(days=i)
            if target_day.date() > datetime.now().date(): break
            
            try:
                await asyncio.sleep(0.5)
                data = await api.async_get_history_hourly(meter_id, target_day)
                
                day_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=tz)
                
                daily_run_imp = 0.0
                daily_run_exp = 0.0
                
                for h, val in enumerate(data.get("import", [])):
                    if val >= 0:
                        dt_hour = day_start + timedelta(hours=h+1)
                        if dt_hour <= datetime.now(tz):
                            daily_run_imp += val
                            all_imp_data.append({
                                "dt": dt_hour, "val": val, "daily_state": daily_run_imp
                            })
                
                for h, val in enumerate(data.get("export", [])):
                    if val >= 0:
                        dt_hour = day_start + timedelta(hours=h+1)
                        if dt_hour <= datetime.now(tz):
                            daily_run_exp += val
                            all_exp_data.append({
                                "dt": dt_hour, "val": val, "daily_state": daily_run_exp
                            })
                            
            except Exception as e: 
                _LOGGER.error(f"Energa Import Fetch Error ({target_day}): {e}")

        def process_and_import(data_list, anchor_sum, eid_total, eid_daily, name_suffix):
            if not data_list: return 0
            
            if anchor_sum <= 0:
                 msg = f"POMINIĘTO import {name_suffix} dla {serial} - Brak poprawnego punktu odniesienia (Anchor=0)."
                 _LOGGER.warning(msg)
                 persistent_notification.async_create(hass, msg, title="Energa: Ochrona Danych", notification_id=f"energa_skip_{meter_id}_{name_suffix}")
                 return 0

            data_list.sort(key=lambda x: x["dt"], reverse=True)
            running_sum = anchor_sum
            
            stats_total = []
            stats_daily = []
            
            for item in data_list:
                dt = item["dt"]
                val = item["val"]
                d_state = item["daily_state"]
                
                stats_total.append(StatisticData(start=dt, state=running_sum, sum=running_sum))
                stats_daily.append(StatisticData(start=dt, state=d_state, sum=running_sum))
                
                running_sum -= val
                
            stats_total.sort(key=lambda x: x["start"])
            stats_daily.sort(key=lambda x: x["start"])
            
            # FIX v3.6.0-beta.1: Added mean_type=None to remove deprecation warning
            if eid_total:
                async_import_statistics(hass, StatisticMetaData(
                    has_mean=False, has_sum=True, name=None, source='recorder', statistic_id=eid_total,
                    unit_of_measurement="kWh", unit_class="energy", mean_type=StatisticType.SUM
                ), stats_total)
                
            if eid_daily:
                async_import_statistics(hass, StatisticMetaData(
                    has_mean=False, has_sum=True, name=None, source='recorder', statistic_id=eid_daily, 
                    unit_of_measurement="kWh", unit_class="energy", mean_type=StatisticType.SUM
                ), stats_daily)
                
            return len(data_list)

        cnt_imp = process_and_import(all_imp_data, anchor_imp, entity_id_imp, entity_id_imp_daily, "Import")
        cnt_exp = process_and_import(all_exp_data, anchor_exp, entity_id_exp, entity_id_exp_daily, "Export")

        success_count = cnt_imp + cnt_exp
        _LOGGER.info(f"Energa [{serial}]: Zakończono import v3.5.24. Importowano punktów: {success_count}. Encje: _v3")

        persistent_notification.async_create(
            hass,
            f"Zakończono pobieranie historii dla {serial}. Punktów: {success_count}. Reset: v3.",
            title="Energa Mobile: Sukces",
            notification_id=f"energa_import_done_{meter_id}"
        )
    except Exception as e:
        _LOGGER.error(f"Energa Import CRASH: {e}", exc_info=True)
        persistent_notification.async_create(
            hass,
            f"Krytyczny błąd importu: {e}. Sprawdź logi.",
            title="Energa Mobile: Błąd",
            notification_id=f"energa_import_crash_{meter_id}"
        )

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok