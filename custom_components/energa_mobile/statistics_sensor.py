"""Invisible statistics sensor for Energy Dashboard integration.

This module implements sensors that have no visible state (always "Unknown")
but populate Home Assistant's statistics database with hourly energy data.

Based on architectural pattern from hass-energa-my-meter (thedeemling).
Key insight: Separating visible state from statistics import eliminates
midnight reset spike issues.
"""
from datetime import datetime
import logging
from typing import override

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)


class EnergaStatisticsSensor(CoordinatorEntity):
    """Invisible sensor for hourly energy statistics (Energy Dashboard only).
    
    This sensor intentionally has no visible state (always shows "Unknown").
    It exists solely to import hourly statistics into HA's recorder database
    via async_import_statistics.
    
    Benefits:
    - Midnight resets invisible to HA (no state change detected)
    - Hourly granularity from mainChart API endpoint
    - No TOTAL_INCREASING constraint violations
    - Proper Energy Dashboard integration
    """

    def __init__(
        self,
        coordinator,
        meter_id: str,
        data_key: str,
        name: str,
        device_info: DeviceInfo,
    ):
        """Initialize statistics sensor."""
        super().__init__(coordinator)
        
        self._meter_id = meter_id
        self._data_key = data_key  # "import" or "export"
        self._attr_name = name
        self._attr_unique_id = f"{meter_id}_{data_key}_statistics"
        self._attr_has_entity_name = True
        
        # Critical: state_class = TOTAL (not TOTAL_INCREASING)
        # This allows us to import historical points without monotonic increase requirement
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_info = device_info
        
        # Icon
        self._attr_icon = "mdi:chart-line" if data_key == "import" else "mdi:solar-power"
        
        _LOGGER.debug(
            "Created statistics sensor: %s (meter=%s, key=%s)",
            self.entity_id, meter_id, data_key
        )

    @property
    def native_value(self):
        """Return None - this sensor has no visible state.
        
        The sensor will always show as "Unknown" in the UI.
        This is intentional and required for proper statistics import.
        """
        return None

    @property
    def available(self) -> bool:
        """Sensor is always unavailable (by design)."""
        return False

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Import hourly statistics when coordinator updates.
        
        This bypasses the normal state update mechanism and directly
        populates HA's statistics database with hourly data points.
        """
        _LOGGER.debug(
            "Statistics sensor %s: Handling coordinator update",
            self.entity_id
        )
        
        # Get hourly statistics from coordinator
        hourly_stats = self.coordinator.get_hourly_statistics(
            self._meter_id, self._data_key
        )
        
        if not hourly_stats:
            _LOGGER.debug(
                "No hourly statistics available for %s (meter=%s, key=%s)",
                self.entity_id, self._meter_id, self._data_key
            )
            super()._handle_coordinator_update()
            return
        
        # Prepare metadata for statistics import
        metadata = StatisticMetaData(
            source="recorder",
            statistic_id=self.entity_id,
            name=self._attr_name,
            unit_of_measurement=self._attr_native_unit_of_measurement,
            has_mean=False,
            has_sum=True,
        )
        
        _LOGGER.info(
            "Importing %d hourly statistics for %s (range: %s to %s)",
            len(hourly_stats),
            self.entity_id,
            hourly_stats[0]["start"] if hourly_stats else "N/A",
            hourly_stats[-1]["start"] if hourly_stats else "N/A"
        )
        
        # Import statistics directly into recorder (bypass state)
        async_import_statistics(self.hass, metadata, hourly_stats)
        
        # Call parent to trigger entity update (but state remains None)
        super()._handle_coordinator_update()
