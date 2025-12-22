"""Energa Mobile integration v4.0.0.

Clean rebuild with simplified architecture:
- Statistics sensors only (for Energy Dashboard)
- No self-healing (manual fetch_history service)
- Active meter filtering
"""
import asyncio
from datetime import datetime, timedelta
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
from homeassistant.components import persistent_notification

from .api import EnergaAPI, EnergaAuthError, EnergaConnectionError, EnergaTokenExpiredError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]
TIMEZONE = ZoneInfo("Europe/Warsaw")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energa Mobile from config entry."""
    session = async_get_clientsession(hass)
    api = EnergaAPI(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session)

    # Login to API
    try:
        await api.async_login()
    except EnergaAuthError as err:
        raise ConfigEntryAuthFailed(err) from err
    except EnergaTokenExpiredError:
        _LOGGER.warning("Token expired during setup, retrying login")
        try:
            await api.async_login()
        except EnergaAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except EnergaConnectionError as err:
            raise ConfigEntryNotReady(err) from err
    except EnergaConnectionError as err:
        raise ConfigEntryNotReady(err) from err

    # Store API instance
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register fetch_history service
    async def fetch_history_service(call: ServiceCall) -> None:
        """Service to manually fetch historical data."""
        start_date_str = call.data["start_date"]
        days = call.data.get("days", 30)

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            _LOGGER.error("Invalid date format: %s (expected YYYY-MM-DD)", start_date_str)
            persistent_notification.async_create(
                hass,
                f"Błędny format daty: {start_date_str}",
                title="Energa: Błąd",
                notification_id="energa_fetch_error",
            )
            return

        # Get fresh meter data
        try:
            meters = await api.async_get_data(force_refresh=True)
        except Exception as err:
            _LOGGER.error("Failed to fetch meter data: %s", err)
            persistent_notification.async_create(
                hass,
                f"Nie można pobrać danych licznika: {err}",
                title="Energa: Błąd",
                notification_id="energa_fetch_error",
            )
            return

        # Filter active meters
        active_meters = [
            m for m in meters 
            if m.get("total_plus") and float(m.get("total_plus", 0)) > 0
        ]

        if not active_meters:
            _LOGGER.warning("No active meters found")
            persistent_notification.async_create(
                hass,
                "Nie znaleziono aktywnych liczników",
                title="Energa: Ostrzeżenie",
                notification_id="energa_fetch_warning",
            )
            return

        # Process each active meter
        for meter in active_meters:
            hass.async_create_task(
                _import_meter_history(hass, api, meter, start_date, days)
            )

    hass.services.async_register(
        DOMAIN,
        "fetch_history",
        fetch_history_service,
        schema=vol.Schema({
            vol.Required("start_date"): str,
            vol.Optional("days", default=30): int,
        }),
    )

    return True


async def _import_meter_history(
    hass: HomeAssistant,
    api: EnergaAPI,
    meter: dict,
    start_date: datetime,
    days: int,
) -> None:
    """Import historical data for a single meter."""
    meter_id = meter["meter_point_id"]
    serial = meter.get("meter_serial", meter_id)

    _LOGGER.info("Starting history import for meter %s (%d days from %s)", 
                 serial, days, start_date.date())

    # Show start notification
    persistent_notification.async_create(
        hass,
        f"Rozpoczęto pobieranie historii dla licznika {serial}\n"
        f"Zakres: {days} dni od {start_date.date()}",
        title="Energa: Import Historii",
        notification_id=f"energa_import_{meter_id}",
    )

    try:
        # Get current meter readings as anchor
        anchor_import = float(meter.get("total_plus", 0))
        anchor_export = float(meter.get("total_minus", 0))

        if anchor_import <= 0:
            _LOGGER.error("Invalid anchor for import (total_plus=0)")
            persistent_notification.async_create(
                hass,
                f"Brak punktu odniesienia dla licznika {serial}",
                title="Energa: Błąd",
                notification_id=f"energa_import_{meter_id}",
            )
            return

        # Collect all hourly data
        import_points = []
        export_points = []

        for day_offset in range(days):
            target_day = start_date + timedelta(days=day_offset)
            if target_day.date() > datetime.now().date():
                break

            # Rate limiting
            await asyncio.sleep(0.5)

            try:
                day_data = await api.async_get_history_hourly(meter_id, target_day)
            except Exception as err:
                _LOGGER.warning("Failed to fetch day %s: %s", target_day.date(), err)
                continue

            day_start = target_day.replace(
                hour=0, minute=0, second=0, microsecond=0,
                tzinfo=TIMEZONE
            )

            # Process import data
            for hour_idx, hourly_value in enumerate(day_data.get("import", [])):
                if hourly_value and hourly_value >= 0:
                    hour_dt = day_start + timedelta(hours=hour_idx + 1)
                    import_points.append({
                        "dt": hour_dt,
                        "value": hourly_value,
                    })

            # Process export data
            for hour_idx, hourly_value in enumerate(day_data.get("export", [])):
                if hourly_value and hourly_value >= 0:
                    hour_dt = day_start + timedelta(hours=hour_idx + 1)
                    export_points.append({
                        "dt": hour_dt,
                        "value": hourly_value,
                    })

        # Build statistics with cumulative sums (working backwards from anchor)
        def build_statistics(points: list, anchor: float, entity_suffix: str) -> int:
            if not points or anchor <= 0:
                return 0

            # Sort newest first for backward calculation
            points.sort(key=lambda x: x["dt"], reverse=True)
            
            running_sum = anchor
            statistics = []
            
            for point in points:
                statistics.append(
                    StatisticData(
                        start=point["dt"],
                        sum=running_sum,
                        state=point["value"],
                    )
                )
                running_sum -= point["value"]

            # Sort oldest first for import
            statistics.sort(key=lambda x: x["start"])

            # Find entity ID
            ent_reg = er.async_get(hass)
            uid = f"energa_{meter_id}_{entity_suffix}_stats"
            entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
            
            if not entity_id:
                entity_id = f"sensor.energa_{meter_id}_{entity_suffix}_stats"

            # Import statistics
            metadata = StatisticMetaData(
                source="recorder",
                statistic_id=entity_id,
                name=None,
                unit_of_measurement="kWh",
                has_mean=False,
                has_sum=True,
            )

            async_import_statistics(hass, metadata, statistics)
            _LOGGER.info("Imported %d statistics for %s", len(statistics), entity_id)
            return len(statistics)

        count_import = build_statistics(import_points, anchor_import, "import")
        count_export = build_statistics(export_points, anchor_export, "export")

        total_count = count_import + count_export
        
        # Show success notification
        persistent_notification.async_create(
            hass,
            f"Zakończono import dla licznika {serial}\n"
            f"Zaimportowano {total_count} punktów danych\n"
            f"(Import: {count_import}, Export: {count_export})",
            title="Energa: Sukces",
            notification_id=f"energa_import_{meter_id}",
        )

        _LOGGER.info("History import complete for %s: %d points", serial, total_count)

    except Exception as err:
        _LOGGER.error("History import failed for %s: %s", serial, err, exc_info=True)
        persistent_notification.async_create(
            hass,
            f"Błąd importu historii dla {serial}: {err}",
            title="Energa: Błąd",
            notification_id=f"energa_import_{meter_id}",
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok