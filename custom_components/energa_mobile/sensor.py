"""Sensor platform for Energa Mobile v4.0.0.

Clean rebuild based on thedeemling/hass-energa-my-meter architecture.
Implements invisible statistics sensors for Energy Dashboard integration.
"""
from datetime import timedelta, datetime
import logging
from typing import override
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics, get_last_statistics
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
)
from homeassistant.loader import async_get_integration

from .api import EnergaAuthError, EnergaConnectionError, EnergaTokenExpiredError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Timezone for Energa data
TIMEZONE = ZoneInfo("Europe/Warsaw")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energa sensors from config entry."""
    api = hass.data[DOMAIN][entry.entry_id]
    
    # Get integration version for device info
    integration = await async_get_integration(hass, DOMAIN)
    sw_version = str(integration.version)  # Must be string for AwesomeVersion
    
    # Create coordinator
    coordinator = EnergaCoordinator(hass, api)
    
    # Initial data fetch
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Energa: Initial fetch failed, will retry: %s", err)
    
    if not coordinator.data:
        _LOGGER.warning("No meter data available at startup")
        return
    
    # Create sensors for each meter
    sensors = []
    for meter in coordinator.data:
        meter_id = meter["meter_point_id"]
        serial = meter.get("meter_serial", meter_id)
        ppe = meter.get("ppe", meter_id)
        
        device_info = DeviceInfo(
            identifiers={(DOMAIN, str(serial))},
            name=f"Energa {serial}",
            manufacturer="Energa-Operator",
            model=f"PPE: {ppe}",
            configuration_url="https://mojlicznik.energa-operator.pl",
            sw_version=sw_version,
        )
        
        # === LIVE SENSORS (4 visible, show actual meter readings) ===
        
        # 1. Total Import (Grid consumption - lifetime counter)
        sensors.append(
            EnergaLiveSensor(
                coordinator=coordinator,
                meter_id=meter_id,
                data_key="total_plus",
                name="Stan Licznika Import",
                icon="mdi:counter",
                device_info=device_info,
            )
        )
        
        # 2. Total Export (Production to grid - lifetime counter)
        if meter.get("total_minus"):
            sensors.append(
                EnergaLiveSensor(
                    coordinator=coordinator,
                    meter_id=meter_id,
                    data_key="total_minus",
                    name="Stan Licznika Export",
                    icon="mdi:counter",
                    device_info=device_info,
                )
            )
        
        # 3. Daily Import (Today's consumption - resets at midnight)
        sensors.append(
            EnergaLiveSensor(
                coordinator=coordinator,
                meter_id=meter_id,
                data_key="daily_pobor",
                name="Zużycie Dziś",
                icon="mdi:flash",
                device_info=device_info,
                state_class_override=SensorStateClass.TOTAL,  # Daily resets, not INCREASING
            )
        )
        
        # 4. Daily Export (Today's production - resets at midnight)
        if meter.get("obis_minus"):
            sensors.append(
                EnergaLiveSensor(
                    coordinator=coordinator,
                    meter_id=meter_id,
                    data_key="daily_produkcja",
                    name="Produkcja Dziś",
                    icon="mdi:solar-power",
                    device_info=device_info,
                    state_class_override=SensorStateClass.TOTAL,  # Daily resets, not INCREASING
                )
            )
        
        # === STATISTICS SENSORS (2 invisible, for Energy Dashboard) ===
        
        # 5. Panel Import (hourly statistics for Energy Dashboard)
        sensors.append(
            EnergaStatisticsSensor(
                coordinator=coordinator,
                meter_id=meter_id,
                data_key="import",
                name="Panel Energia Zużycie",
                device_info=device_info,
            )
        )
        
        # 6. Panel Export (hourly statistics for Energy Dashboard)
        if meter.get("obis_minus"):
            sensors.append(
                EnergaStatisticsSensor(
                    coordinator=coordinator,
                    meter_id=meter_id,
                    data_key="export",
                    name="Panel Energia Produkcja",
                    device_info=device_info,
                )
            )
    
    _LOGGER.info("Created %d Energa sensors (4 live + 2 statistics)", len(sensors))
    async_add_entities(sensors, update_before_add=True)


class EnergaCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching Energa data."""

    def __init__(self, hass: HomeAssistant, api) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Energa Mobile",
            update_interval=timedelta(hours=1),  # Hourly updates
        )
        self.api = api
        self._hourly_stats: dict = {}  # {meter_id: {"import": [...], "export": [...]}}

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            # Fetch meter data
            meters = await self.api.async_get_data()
            
            # Filter out meters that return errors (like 300302)
            active_meters = []
            for meter in meters:
                meter_id = meter.get("meter_point_id")
                # Check if meter has valid data (total_plus should be > 0 for active meter)
                if meter.get("total_plus") and float(meter.get("total_plus", 0)) > 0:
                    active_meters.append(meter)
                else:
                    _LOGGER.debug("Skipping meter %s - no valid data", meter_id)
            
            # Fetch hourly statistics for active meters
            for meter in active_meters:
                meter_id = meter["meter_point_id"]
                try:
                    stats = await self.api.async_get_hourly_statistics(meter_id, days_back=2)
                    self._hourly_stats[meter_id] = stats
                except Exception as err:
                    _LOGGER.warning("Failed to fetch hourly stats for %s: %s", meter_id, err)
                    self._hourly_stats[meter_id] = {"import": [], "export": []}
            
            return active_meters

        except EnergaTokenExpiredError:
            _LOGGER.warning("Token expired, attempting re-login")
            try:
                await self.api.async_login()
                return await self._async_update_data()
            except EnergaAuthError as err:
                raise UpdateFailed(f"Auth error after token refresh: {err}") from err

        except EnergaConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def get_hourly_stats(self, meter_id: str, data_key: str) -> list:
        """Get hourly statistics for a meter."""
        meter_stats = self._hourly_stats.get(meter_id, {})
        return meter_stats.get(data_key, [])


class EnergaLiveSensor(CoordinatorEntity, SensorEntity):
    """Live sensor showing actual meter readings.
    
    This sensor displays the current total meter reading (lifetime counter)
    and is visible in the UI. Use this for monitoring actual consumption/production.
    """

    def __init__(
        self,
        coordinator,
        meter_id: str,
        data_key: str,
        name: str,
        icon: str,
        device_info: DeviceInfo,
        state_class_override: SensorStateClass = None,
    ) -> None:
        """Initialize live sensor."""
        super().__init__(coordinator)
        
        self._meter_id = meter_id
        self._data_key = data_key
        
        # Entity attributes
        self._attr_name = name
        self._attr_unique_id = f"energa_{meter_id}_{data_key}_live"
        self._attr_has_entity_name = True
        
        # Sensor class attributes
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = state_class_override or SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        
        # Device info
        self._attr_device_info = device_info
        
        # Icon
        self._attr_icon = icon

    @property
    def native_value(self):
        """Return current meter reading from API."""
        if not self.coordinator.data:
            _LOGGER.debug("LiveSensor %s: No coordinator data", self._attr_name)
            return None
        
        # Find meter data
        for meter in self.coordinator.data:
            # Compare as strings to avoid type mismatch
            if str(meter.get("meter_point_id")) == str(self._meter_id):
                value = meter.get(self._data_key)
                _LOGGER.debug(
                    "LiveSensor %s: Found meter %s, key=%s, value=%s",
                    self._attr_name, self._meter_id, self._data_key, value
                )
                if value is not None:
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return None
        
        _LOGGER.debug("LiveSensor %s: Meter %s not found in data", self._attr_name, self._meter_id)
        return None

    @property
    def available(self) -> bool:
        """Sensor is available when we have data."""
        return self.coordinator.data is not None and self.native_value is not None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}

        for meter in self.coordinator.data:
            if str(meter.get("meter_point_id")) == str(self._meter_id):
                return {
                    "adres": meter.get("address"),
                    "taryfa": meter.get("tariff"),
                    "ppe": meter.get("ppe"),
                    "numer_licznika": meter.get("meter_serial"),
                    "data_umowy": str(meter.get("contract_date")) if meter.get("contract_date") else None,
                }
        return {}

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("LiveSensor %s: Coordinator update, value=%s", 
                     self._attr_name, self.native_value)
        self.async_write_ha_state()


class EnergaStatisticsSensor(CoordinatorEntity):
    """Statistics sensor for Energy Dashboard.
    
    This sensor has no visible state (always "Unknown") and exists only
    to import hourly statistics into Home Assistant's recorder database.
    
    Based on pattern from thedeemling/hass-energa-my-meter.
    """

    def __init__(
        self,
        coordinator: EnergaCoordinator,
        meter_id: str,
        data_key: str,
        name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize statistics sensor."""
        super().__init__(coordinator)
        
        self._meter_id = meter_id
        self._data_key = data_key
        
        # Entity attributes
        self._attr_name = name
        self._attr_unique_id = f"energa_{meter_id}_{data_key}_stats"
        self._attr_has_entity_name = True
        
        # Sensor class attributes
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        
        # Device info
        self._attr_device_info = device_info
        
        # Icon based on type
        self._attr_icon = "mdi:transmission-tower" if data_key == "import" else "mdi:solar-power"
        
        # This sensor has no state - it's "Unknown" by design
        self._attr_native_value = None

    @property
    def available(self) -> bool:
        """Sensor is always unavailable by design.
        
        This is intentional - statistics sensors should show as "Unknown"
        and only be used for Energy Dashboard, not UI display.
        """
        return False

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update - import statistics to recorder."""
        _LOGGER.debug("Updating statistics for %s", self.entity_id)
        
        # Get hourly data from coordinator
        hourly_stats = self.coordinator.get_hourly_stats(self._meter_id, self._data_key)
        
        if not hourly_stats:
            _LOGGER.debug("No hourly stats available for %s", self.entity_id)
            super()._handle_coordinator_update()
            return
        
        # Build StatisticData list
        statistics_data = []
        for point in hourly_stats:
            try:
                statistics_data.append(
                    StatisticData(
                        start=point["start"],
                        sum=point["sum"],
                        state=point.get("state", 0),
                    )
                )
            except (KeyError, TypeError) as err:
                _LOGGER.warning("Invalid stat point: %s", err)
                continue
        
        if not statistics_data:
            super()._handle_coordinator_update()
            return
        
        # Prepare metadata
        metadata = StatisticMetaData(
            source="recorder",
            statistic_id=self.entity_id,
            name=self._attr_name,
            unit_of_measurement=self._attr_native_unit_of_measurement,
            has_mean=False,
            has_sum=True,
        )
        
        # Import statistics
        _LOGGER.info(
            "Importing %d statistics for %s (range: %s to %s)",
            len(statistics_data),
            self.entity_id,
            statistics_data[0]["start"] if statistics_data else "N/A",
            statistics_data[-1]["start"] if statistics_data else "N/A",
        )
        
        async_import_statistics(self.hass, metadata, statistics_data)
        
        # Call parent update
        super()._handle_coordinator_update()