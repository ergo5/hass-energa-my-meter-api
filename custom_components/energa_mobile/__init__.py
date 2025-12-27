"""Energa Mobile integration v4.0.0.

Clean rebuild with simplified architecture:
- Statistics sensors only (for Energy Dashboard)
- No self-healing (manual fetch_history service)
- Active meter filtering
"""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import (
    EnergaAPI,
    EnergaAuthError,
    EnergaConnectionError,
    EnergaTokenExpiredError,
)
from .const import (
    CONF_DEVICE_TOKEN,
    CONF_EXPORT_PRICE,
    CONF_IMPORT_PRICE,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]
TIMEZONE = ZoneInfo("Europe/Warsaw")
UTC = ZoneInfo("UTC")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energa Mobile from config entry."""
    session = async_get_clientsession(hass)

    # Get device token from config (may not exist in old installations)
    import secrets

    device_token = entry.data.get(CONF_DEVICE_TOKEN) or secrets.token_hex(32)
    api = EnergaAPI(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], device_token, session
    )

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

    # Set hass reference for statistics queries
    api.set_hass(hass)

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
            _LOGGER.error(
                "Invalid date format: %s (expected YYYY-MM-DD)", start_date_str
            )
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
            m
            for m in meters
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
                _import_meter_history(hass, api, meter, start_date, days, entry)
            )

    hass.services.async_register(
        DOMAIN,
        "fetch_history",
        fetch_history_service,
        schema=vol.Schema(
            {
                vol.Required("start_date"): str,
                vol.Optional("days", default=30): int,
            }
        ),
    )

    return True


async def _import_meter_history(
    hass: HomeAssistant,
    api: EnergaAPI,
    meter: dict,
    start_date: datetime,
    days: int,
    entry: ConfigEntry,
) -> None:
    """Import historical data for a single meter."""
    # Use meter_serial for entity_id (real meter number, e.g. 30132815)
    # meter_point_id is API-internal (e.g. 300302), only used for API calls
    meter_point_id = meter["meter_point_id"]  # For API calls
    meter_id = meter.get(
        "meter_serial", meter_point_id
    )  # For entity_id (real meter number)
    serial = meter_id  # For notifications

    _LOGGER.info(
        "Starting history import for meter %s (%d days from %s)",
        serial,
        days,
        start_date.date(),
    )

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
        anchor_import = float(meter.get("total_plus") or 0)
        anchor_export = float(meter.get("total_minus") or 0)

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
            target_day = (start_date + timedelta(days=day_offset)).replace(
                tzinfo=TIMEZONE
            )
            if target_day.date() > datetime.now().date():
                break

            # Rate limiting
            await asyncio.sleep(0.5)

            try:
                day_data = await api.async_get_history_hourly(
                    meter_point_id, target_day
                )
            except Exception as err:
                _LOGGER.warning("Failed to fetch day %s: %s", target_day.date(), err)
                continue

            day_start = target_day.replace(hour=0, minute=0, second=0, microsecond=0)

            # Process import data
            for hour_idx, hourly_value in enumerate(day_data.get("import", [])):
                if hourly_value and hourly_value >= 0:
                    hour_dt = dt_util.as_utc(day_start + timedelta(hours=hour_idx + 1))
                    import_points.append(
                        {
                            "dt": hour_dt,
                            "value": hourly_value,
                        }
                    )

            # Process export data
            for hour_idx, hourly_value in enumerate(day_data.get("export", [])):
                if hourly_value and hourly_value >= 0:
                    hour_dt = dt_util.as_utc(day_start + timedelta(hours=hour_idx + 1))
                    export_points.append(
                        {
                            "dt": hour_dt,
                            "value": hourly_value,
                        }
                    )

        _LOGGER.info(
            "Collected data for meter %s: %d import points, %d export points",
            serial,
            len(import_points),
            len(export_points),
        )

        # Build statistics with intelligent initialization (forward calculation)
        def build_statistics(
            points: list, anchor: float, entity_suffix: str, entry: ConfigEntry
        ) -> int:
            if not points or anchor <= 0:
                return 0

            # Get price from config options
            if entity_suffix == "import":
                price = entry.options.get(CONF_IMPORT_PRICE, 1.188)
            else:  # export
                price = entry.options.get(CONF_EXPORT_PRICE, 0.95)

            # Sort oldest first for forward calculation
            points.sort(key=lambda x: x["dt"])

            # INTELLIGENT INITIALIZATION: Query last sum from database or calculate base
            from homeassistant.components.recorder.statistics import (
                get_last_statistics,
            )

            # Build entity_id
            if entity_suffix == "import":
                energy_sensor_name = "energa_zuzycie"
            else:
                energy_sensor_name = "energa_produkcja"

            entity_id = f"sensor.energa_{meter_id}_{energy_sensor_name}"

            # Query last statistics sum (direct sync call)
            running_sum = 0.0  # Fallback

            try:
                # get_last_statistics is SYNC - call directly!
                last_stats_result = get_last_statistics(
                    hass, 1, entity_id, True, {"sum"}
                )

                if entity_id in last_stats_result and last_stats_result[entity_id]:
                    last_sum = last_stats_result[entity_id][0].get("sum")
                    if last_sum is not None:
                        # INCREMENTAL: Continue from last known sum
                        running_sum = last_sum
                        _LOGGER.info(
                            "Statistics: Continuing from last sum=%.3f for %s",
                            running_sum,
                            entity_id,
                        )
                    else:
                        # FIRST IMPORT: Calculate base so final sum = anchor
                        total_to_import = sum(p["value"] for p in points)
                        running_sum = anchor - total_to_import
                        _LOGGER.info(
                            "Statistics: First import for %s, base=%.3f (anchor=%.3f - import=%.3f)",
                            entity_id,
                            running_sum,
                            anchor,
                            total_to_import,
                        )
                else:
                    # NO PREVIOUS DATA: Calculate base
                    total_to_import = sum(p["value"] for p in points)
                    running_sum = anchor - total_to_import
                    _LOGGER.info(
                        "Statistics: No previous data for %s, base=%.3f (anchor=%.3f)",
                        entity_id,
                        running_sum,
                        anchor,
                    )
            except Exception as e:
                # FALLBACK: Calculate base
                total_to_import = sum(p["value"] for p in points)
                running_sum = anchor - total_to_import
                _LOGGER.warning(
                    "Failed to query last statistics for %s, using calculated base=%.3f: %s",
                    entity_id,
                    running_sum,
                    e,
                )

            # Build energy statistics (FORWARD)
            statistics = []
            for point in points:
                running_sum += point["value"]
                statistics.append(
                    {
                        "start": point["dt"],
                        "sum": running_sum,
                        "state": point["value"],
                    }
                )

            # Build cost statistics (forward, cumulative)
            cost_sum = 0.0
            cost_statistics = []
            for stat in statistics:
                hourly_energy = stat["state"] or 0
                hourly_cost = hourly_energy * price
                cost_sum += hourly_cost
                cost_statistics.append(
                    {
                        "start": stat["start"],
                        "sum": cost_sum,
                        "state": hourly_cost,
                    }
                )

            # Import energy statistics
            metadata = StatisticMetaData(
                source="recorder",
                statistic_id=entity_id,
                name=None,
                unit_of_measurement="kWh",
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
            )

            async_import_statistics(hass, metadata, statistics)
            _LOGGER.info(
                "Imported %d energy statistics for %s", len(statistics), entity_id
            )

            # Import cost statistics to matching cost sensor
            cost_entity_id = f"{entity_id}_cost"
            cost_name = (
                "Panel Energia Zużycie Koszt"
                if entity_suffix == "import"
                else "Panel Energia Produkcja Rekompensata"
            )

            cost_metadata = StatisticMetaData(
                source="recorder",
                statistic_id=cost_entity_id,
                name=cost_name,
                unit_of_measurement="PLN",
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
            )

            async_import_statistics(hass, cost_metadata, cost_statistics)
            _LOGGER.info(
                "Imported %d cost statistics for %s (price: %.3f PLN/kWh)",
                len(cost_statistics),
                cost_entity_id,
                price,
            )

            return len(statistics)

        count_import = build_statistics(import_points, anchor_import, "import", entry)
        count_export = build_statistics(export_points, anchor_export, "export", entry)

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
