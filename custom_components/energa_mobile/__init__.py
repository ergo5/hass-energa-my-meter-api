"""Energa My Meter integration.

Clean rebuild with simplified architecture:
- Statistics sensors with zone support (G12w: strefa 1 + strefa 2)
- No self-healing (manual fetch_history service)
- Active meter filtering
"""

import asyncio
import logging
import secrets

import aiohttp
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.components.recorder.models import (
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.util import dt as dt_util

from .api import (
    EnergaAPI,
    EnergaAuthError,
    EnergaConnectionError,
    EnergaTokenExpiredError,
)
from .const import (
    CONF_DEVICE_TOKEN,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    get_price_for_key,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]
TIMEZONE = ZoneInfo("Europe/Warsaw")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energa My Meter from config entry."""
    # Use dedicated session to avoid clearing cookies on the shared HA session
    session = aiohttp.ClientSession()

    # Get device token from config (may not exist in old installations)
    device_token = entry.data.get(CONF_DEVICE_TOKEN) or secrets.token_hex(32)
    api = EnergaAPI(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        device_token,
        session,
        create_session_fn=lambda: aiohttp.ClientSession(),
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
    hass.data[DOMAIN][entry.entry_id] = {"api": api, "session": session}

    # Close session when HA shuts down
    async def _close_session(_event):
        await session.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _close_session)
    )

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
            await _import_meter_history(hass, api, meter, start_date, days, entry)

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
    """Import historical data for a single meter.

    Supports multi-zone tariffs (G12w): imports zone-specific statistics.
    """
    meter_point_id = meter["meter_point_id"]
    meter_id = meter.get("meter_serial", meter_point_id)
    serial = meter_id
    has_zones = meter.get("zone_count", 1) > 1

    _LOGGER.info(
        "Starting history import for meter %s (%d days from %s, zones=%s)",
        serial,
        days,
        start_date.date(),
        has_zones,
    )

    persistent_notification.async_create(
        hass,
        f"Rozpoczęto pobieranie historii dla licznika {serial}\n"
        f"Zakres: {days} dni od {start_date.date()}"
        + (f"\nTaryfa wielostrefowa: {meter.get('tariff')}" if has_zones else ""),
        title="Energa: Import Historii",
        notification_id=f"energa_import_{meter_id}",
    )

    try:
        # Collect all hourly data
        import_points = []
        import_1_points = []
        import_2_points = []
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

            # Process import data (total)
            for hour_idx, hourly_value in enumerate(day_data.get("import", [])):
                if hourly_value is not None and hourly_value >= 0:
                    hour_dt = dt_util.as_utc(day_start + timedelta(hours=hour_idx))
                    import_points.append({"dt": hour_dt, "value": hourly_value})

            # Process zone-specific import data
            if has_zones:
                for hour_idx, hourly_value in enumerate(day_data.get("import_1", [])):
                    if hourly_value is not None and hourly_value >= 0:
                        hour_dt = dt_util.as_utc(day_start + timedelta(hours=hour_idx))
                        import_1_points.append({"dt": hour_dt, "value": hourly_value})

                for hour_idx, hourly_value in enumerate(day_data.get("import_2", [])):
                    if hourly_value is not None and hourly_value >= 0:
                        hour_dt = dt_util.as_utc(day_start + timedelta(hours=hour_idx))
                        import_2_points.append({"dt": hour_dt, "value": hourly_value})

            # Process export data
            for hour_idx, hourly_value in enumerate(day_data.get("export", [])):
                if hourly_value is not None and hourly_value >= 0:
                    hour_dt = dt_util.as_utc(day_start + timedelta(hours=hour_idx))
                    export_points.append({"dt": hour_dt, "value": hourly_value})

        _LOGGER.info(
            "Collected data for meter %s: %d import, %d export%s",
            serial,
            len(import_points),
            len(export_points),
            f", zone1={len(import_1_points)}, zone2={len(import_2_points)}"
            if has_zones
            else "",
        )

        def build_statistics(
            points: list, entity_suffix: str, entry: ConfigEntry
        ) -> int:
            if not points:
                return 0

            # Get price from config options
            price = get_price_for_key(dict(entry.options), entity_suffix)

            # Forward calculation from zero - sort oldest first
            points.sort(key=lambda x: x["dt"])

            running_sum = 0.0
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

            # Build cost statistics
            cost_statistics = []
            for stat in statistics:
                hourly_energy = stat["state"] or 0
                hourly_cost = hourly_energy * price
                cost_sum = stat["sum"] * price
                cost_statistics.append(
                    {
                        "start": stat["start"],
                        "sum": cost_sum,
                        "state": hourly_cost,
                    }
                )

            # Map entity suffix to sensor name
            suffix_to_name = {
                "import": "panel_energia_zuzycie",
                "import_1": "panel_energia_strefa_1",
                "import_2": "panel_energia_strefa_2",
                "export": "panel_energia_produkcja",
            }
            energy_sensor_name = suffix_to_name.get(
                entity_suffix, f"panel_{entity_suffix}"
            )
            entity_id = f"sensor.energa_{meter_id}_{energy_sensor_name}"

            # Import energy statistics
            metadata = StatisticMetaData(
                source="recorder",
                statistic_id=entity_id,
                name=None,
                unit_of_measurement="kWh",
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                unit_class="energy",
            )

            async_import_statistics(hass, metadata, statistics)
            _LOGGER.info(
                "Imported %d energy statistics for %s", len(statistics), entity_id
            )

            # Import cost statistics
            cost_entity_id = f"{entity_id}_cost"
            cost_name_map = {
                "import": "Panel Energia Zużycie Koszt",
                "import_1": "Panel Energia Strefa 1 Koszt",
                "import_2": "Panel Energia Strefa 2 Koszt",
                "export": "Panel Energia Produkcja Rekompensata",
            }
            cost_name = cost_name_map.get(entity_suffix, f"Koszt {entity_suffix}")

            cost_metadata = StatisticMetaData(
                source="recorder",
                statistic_id=cost_entity_id,
                name=cost_name,
                unit_of_measurement="PLN",
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                unit_class=None,
            )

            async_import_statistics(hass, cost_metadata, cost_statistics)
            _LOGGER.info(
                "Imported %d cost statistics for %s (price: %.4f PLN/kWh)",
                len(cost_statistics),
                cost_entity_id,
                price,
            )

            return len(statistics)

        # Build and import statistics
        if has_zones:
            count_1 = build_statistics(import_1_points, "import_1", entry)
            count_2 = build_statistics(import_2_points, "import_2", entry)
            count_export = build_statistics(export_points, "export", entry)
            total_count = count_1 + count_2 + count_export

            persistent_notification.async_create(
                hass,
                f"Zakończono import dla licznika {serial}\n"
                f"Zaimportowano {total_count} punktów danych\n"
                f"(Strefa 1: {count_1}, Strefa 2: {count_2}, Export: {count_export})",
                title="Energa: Sukces",
                notification_id=f"energa_import_{meter_id}",
            )
        else:
            count_import = build_statistics(import_points, "import", entry)
            count_export = build_statistics(export_points, "export", entry)
            total_count = count_import + count_export

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
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        # Close dedicated session
        if isinstance(entry_data, dict) and "session" in entry_data:
            await entry_data["session"].close()
        # Unregister service if no more entries remain
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "fetch_history")
    return unload_ok
