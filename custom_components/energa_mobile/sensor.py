"""Sensor platform for Energa My Meter.

Clean rebuild based on thedeemling/hass-energa-my-meter architecture.
Implements invisible statistics sensors for Energy Dashboard integration.
"""

import logging
from datetime import timedelta
from typing import override
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.models import (
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.loader import async_get_integration

from .api import EnergaAuthError, EnergaConnectionError, EnergaTokenExpiredError
from .const import CONF_EXPORT_PRICE, CONF_IMPORT_PRICE, DOMAIN

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
    coordinator = EnergaCoordinator(hass, api, entry)

    # Initial data fetch
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("Energa: Initial refresh successful")
    except Exception as err:
        _LOGGER.warning("Energa: Initial fetch failed, will retry: %s", err)

    # CRITICAL: Fetch meters directly from API to create sensors
    # Don't rely on coordinator.data which may be empty at startup
    try:
        meters_list = await api.async_get_data(force_refresh=False)
        _LOGGER.info(
            "Energa: Fetched %d meters from API for sensor setup",
            len(meters_list) if meters_list else 0,
        )
    except Exception as err:
        _LOGGER.error("Energa: Failed to fetch meters for setup: %s", err)
        meters_list = []

    # Filter active meters (total_plus > 0)
    meters_to_process = (
        [
            m
            for m in meters_list
            if m.get("total_plus") and float(m.get("total_plus", 0)) > 0
        ]
        if meters_list
        else []
    )

    _LOGGER.info(
        "Energa: Creating sensors for %d active meters", len(meters_to_process)
    )

    # Create sensors for each meter
    sensors = []

    for meter in meters_to_process:
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
                entry=entry,
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
                    entry=entry,
                )
            )

        # === INFO SENSORS (Separate entities for details) ===

        info_types = [
            ("address", "Adres", "mdi:map-marker", None),
            ("tariff", "Taryfa", "mdi:cash-multiple", None),
            ("ppe", "PPE", "mdi:identifier", None),
            ("meter_serial", "Numer Licznika", "mdi:counter", None),
            ("contract_date", "Data Aktywacji", "mdi:calendar", None),
        ]

        for key, name, icon, device_class in info_types:
            if meter.get(key):
                sensors.append(
                    EnergaInfoSensor(
                        coordinator=coordinator,
                        meter_id=meter_id,
                        data_key=key,
                        name=f"{name}",
                        icon=icon,
                        device_info=device_info,
                        device_class=device_class,
                    )
                )

    _LOGGER.info("Created %d Energa sensors", len(sensors))
    _LOGGER.debug(
        "Energa: Sensor list: %s",
        [
            s.entity_id if hasattr(s, "entity_id") else s._attr_unique_id
            for s in sensors
        ],
    )
    async_add_entities(sensors, update_before_add=True)


class EnergaCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching Energa data with smart fetch."""

    def __init__(self, hass: HomeAssistant, api, entry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Energa My Meter",
            update_interval=timedelta(hours=1),  # Hourly updates
        )
        self.api = api
        self.entry = entry
        self._hourly_stats: dict = {}  # {meter_id: {"import": [...], "export": [...]}}
        self._pre_fetched_stats: dict = {}  # {entity_id: {"sum": x, "start": dt}}
        self._meter_totals: dict = {}  # {meter_id: {"import": x, "export": y}}

    async def _async_update_data(self):
        """Fetch data from API using smart fetch pattern."""
        try:
            # Fetch meter data
            meters = await self.api.async_get_data()

            # Filter active meters
            active_meters = [
                m
                for m in meters
                if m.get("total_plus") and float(m.get("total_plus", 0)) > 0
            ]

            for meter in active_meters:
                meter_id = meter["meter_point_id"]

                # Store meter totals as anchors for backward calculation
                self._meter_totals[meter_id] = {
                    "import": float(meter.get("total_plus", 0) or 0),
                    "export": float(meter.get("total_minus", 0) or 0),
                }

                # Pre-fetch last statistics for this meter (async-safe)
                await self._fetch_last_stats_for_meter(meter_id)

                # Query last_stat_date for this meter (smart fetch)
                start_date = await self._get_smart_start_date(meter_id)

                try:
                    stats = await self.api.async_get_hourly_statistics(
                        meter_id, start_date=start_date
                    )
                    self._hourly_stats[meter_id] = stats
                except EnergaTokenExpiredError:
                    raise  # Propagate to outer handler for re-login
                except Exception as err:
                    _LOGGER.warning(
                        "Failed to fetch hourly stats for %s: %s", meter_id, err
                    )
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

    async def _get_smart_start_date(self, meter_id: str):
        """Get start_date based on last imported statistic (thedeemling pattern).

        Returns:
            datetime: Start date for fetching (last_stat + 1h, or 30 days ago)
        """
        from datetime import datetime as dt_datetime

        from homeassistant.components.recorder.statistics import get_last_statistics
        from homeassistant.helpers import entity_registry as er
        from homeassistant.util import dt as dt_util

        tz = ZoneInfo("Europe/Warsaw")
        now = dt_datetime.now(tz)
        default_start = now - timedelta(days=30)

        # Find entity_id for this meter's import sensor
        registry = er.async_get(self.hass)
        entity_id = None

        for entity in registry.entities.values():
            if (
                entity.unique_id == f"energa_{meter_id}_import_stats"
                and entity.platform == DOMAIN
            ):
                entity_id = entity.entity_id
                break

        if not entity_id:
            _LOGGER.debug(
                "No entity found for meter %s, using default 30 days", meter_id
            )
            return default_start

        # Query last statistic
        try:
            last_stats = await self.hass.async_add_executor_job(
                get_last_statistics, self.hass, 1, entity_id, True, {"sum"}
            )

            if entity_id in last_stats and last_stats[entity_id]:
                last_ts = last_stats[entity_id][0].get("start")
                if last_ts:
                    # Convert to datetime
                    if isinstance(last_ts, (int, float)):
                        last_dt = dt_util.utc_from_timestamp(last_ts).astimezone(tz)
                    else:
                        last_dt = last_ts.astimezone(tz)

                    # Start from next hour
                    start_date = last_dt + timedelta(hours=1)

                    _LOGGER.debug(
                        "Smart fetch for %s: last_stat=%s, start=%s",
                        entity_id,
                        last_dt,
                        start_date,
                    )
                    return start_date

        except Exception as err:
            _LOGGER.warning("Failed to query last stats for %s: %s", entity_id, err)

        return default_start

    def get_hourly_stats(self, meter_id: str, data_key: str) -> list:
        """Get hourly statistics for a meter."""
        meter_stats = self._hourly_stats.get(meter_id, {})
        return meter_stats.get(data_key, [])

    def get_pre_fetched_stats(self) -> dict:
        """Get pre-fetched last statistics for all entities."""
        return self._pre_fetched_stats

    def get_meter_total(self, meter_id: str, data_key: str) -> float:
        """Get meter total (anchor) for backward calculation."""
        totals = self._meter_totals.get(meter_id, {})
        return totals.get(data_key, 0.0)

    async def _fetch_last_stats_for_meter(self, meter_id: str):
        """Pre-fetch last statistics for meter entities (async-safe)."""
        from homeassistant.components.recorder.statistics import get_last_statistics
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(self.hass)

        # Find Panel Energia sensors for this meter
        for suffix in ["import", "export"]:
            unique_id = f"energa_{meter_id}_{suffix}_stats"

            for entity in registry.entities.values():
                if entity.unique_id == unique_id and entity.platform == DOMAIN:
                    entity_id = entity.entity_id

                    try:
                        last_stats = await self.hass.async_add_executor_job(
                            get_last_statistics,
                            self.hass,
                            1,
                            entity_id,
                            True,
                            {"sum", "start"},
                        )

                        if entity_id in last_stats and last_stats[entity_id]:
                            self._pre_fetched_stats[entity_id] = last_stats[entity_id][
                                0
                            ]
                            _LOGGER.debug(
                                "Pre-fetched stats for %s: sum=%.3f",
                                entity_id,
                                last_stats[entity_id][0].get("sum", 0),
                            )

                            # Also fetch cost sensor
                            cost_entity_id = f"{entity_id}_cost"
                            cost_stats = await self.hass.async_add_executor_job(
                                get_last_statistics,
                                self.hass,
                                1,
                                cost_entity_id,
                                True,
                                {"sum"},
                            )
                            if (
                                cost_entity_id in cost_stats
                                and cost_stats[cost_entity_id]
                            ):
                                self._pre_fetched_stats[cost_entity_id] = cost_stats[
                                    cost_entity_id
                                ][0]

                    except Exception as err:
                        _LOGGER.debug(
                            "Could not pre-fetch stats for %s: %s", entity_id, err
                        )


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
        self._attr_state_class = (
            state_class_override or SensorStateClass.TOTAL_INCREASING
        )
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
                    self._attr_name,
                    self._meter_id,
                    self._data_key,
                    value,
                )
                if value is not None:
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return None

        _LOGGER.debug(
            "LiveSensor %s: Meter %s not found in data", self._attr_name, self._meter_id
        )
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
                    "data_umowy": str(meter.get("contract_date"))
                    if meter.get("contract_date")
                    else None,
                }
        return {}

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "LiveSensor %s: Coordinator update, value=%s",
            self._attr_name,
            self.native_value,
        )
        self.async_write_ha_state()


class EnergaStatisticsSensor(CoordinatorEntity, SensorEntity):
    """Statistics sensor for Energy Dashboard.

    This sensor imports hourly statistics into Home Assistant's recorder database
    and displays the current meter reading as its state.

    Based on pattern from thedeemling/hass-energa-my-meter.
    """

    def __init__(
        self,
        coordinator: EnergaCoordinator,
        meter_id: str,
        data_key: str,
        name: str,
        device_info: DeviceInfo,
        entry: ConfigEntry,
    ) -> None:
        """Initialize statistics sensor."""
        super().__init__(coordinator)

        self._meter_id = meter_id
        self._data_key = data_key
        self._entry = entry  # Store for price access

        # Entity attributes
        self._attr_name = name
        self._attr_unique_id = f"energa_{meter_id}_{data_key}_stats"
        self._attr_has_entity_name = True

        # Sensor class attributes
        self._attr_device_class = SensorDeviceClass.ENERGY
        # NO state_class! We import statistics manually via async_import_statistics.
        # If we set state_class, HA Recorder auto-creates short-term stats from native_value.
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

        # Device info
        self._attr_device_info = device_info

        # Icon based on type
        self._attr_icon = (
            "mdi:transmission-tower" if data_key == "import" else "mdi:solar-power"
        )

    @property
    def native_value(self):
        """Return None - statistics are imported manually, not from state.

        CRITICAL: Do NOT return total_plus/total_minus here!
        If we return a value, HA Recorder will auto-create statistics
        with state=value and sum=0, causing massive spikes on Energy Dashboard.
        """
        return None

    @property
    def available(self) -> bool:
        """Sensor is available when we have data."""
        return self.coordinator.data is not None and self.native_value is not None

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update - import energy and cost statistics to recorder.

        Uses EnergaDataUpdater for proper incremental statistics:
        - Queries last sum from database
        - Incrementally adds hourly values
        - Handles estimates by buffering
        - Deduplicates already-imported points
        """
        from .data_updater import EnergaDataUpdater

        _LOGGER.debug("Updating statistics for %s", self.entity_id)

        # Get hourly data from coordinator
        hourly_stats = self.coordinator.get_hourly_stats(self._meter_id, self._data_key)

        if not hourly_stats:
            _LOGGER.debug("No hourly stats available for %s", self.entity_id)
            super()._handle_coordinator_update()
            return

        # Convert coordinator format to DataUpdater format
        # Coordinator returns: [{"start": dt, "sum": x, "state": y}]
        # DataUpdater expects: [{"dt": dt, "value": y}]
        hourly_data = []
        for point in hourly_stats:
            try:
                hourly_data.append(
                    {
                        "dt": point["start"],
                        "value": point.get("state", 0),
                        "is_estimated": point.get("is_estimated", False),
                    }
                )
            except (KeyError, TypeError) as err:
                _LOGGER.warning("Invalid hourly point: %s", err)
                continue

        if not hourly_data:
            super()._handle_coordinator_update()
            return

        # Use DataUpdater for proper statistics logic
        # Pass pre-fetched stats from Coordinator (async-safe, no blocking calls)
        updater = EnergaDataUpdater(
            self.hass,
            self._entry,
            pre_fetched_stats=self.coordinator.get_pre_fetched_stats(),
        )

        # Get meter total as anchor for backward calculation
        meter_total = self.coordinator.get_meter_total(self._meter_id, self._data_key)

        # CRITICAL: Pass self.entity_id - the ACTUAL entity_id, not a constructed one
        energy_stats, cost_stats = updater.gather_stats_for_sensor(
            meter_id=self._meter_id,
            data_key=self._data_key,
            hourly_data=hourly_data,
            entity_id=self.entity_id,  # Real entity_id from HA
            meter_total=meter_total,
        )

        if not energy_stats:
            _LOGGER.debug("DataUpdater returned no stats for %s", self.entity_id)
            super()._handle_coordinator_update()
            return

        # === IMPORT ENERGY STATISTICS ===
        energy_metadata = StatisticMetaData(
            source="recorder",
            statistic_id=self.entity_id,
            name=self._attr_name,
            unit_of_measurement=self._attr_native_unit_of_measurement,
            has_mean=False,
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
        )

        _LOGGER.info(
            "Importing %d energy statistics for %s",
            len(energy_stats),
            self.entity_id,
        )
        async_import_statistics(self.hass, energy_metadata, energy_stats)

        # === IMPORT COST STATISTICS ===
        if cost_stats:
            cost_entity_id = f"{self.entity_id}_cost"
            cost_name = (
                f"{self._attr_name} Koszt"
                if self._data_key == "import"
                else f"{self._attr_name} Rekompensata"
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

            price = self._entry.options.get(
                CONF_IMPORT_PRICE if self._data_key == "import" else CONF_EXPORT_PRICE,
                1.188 if self._data_key == "import" else 0.95,
            )

            _LOGGER.info(
                "Importing %d cost statistics for %s (price: %.3f PLN/kWh)",
                len(cost_stats),
                cost_entity_id,
                price,
            )
            async_import_statistics(self.hass, cost_metadata, cost_stats)

        # Call parent update
        super()._handle_coordinator_update()


class EnergaInfoSensor(CoordinatorEntity, SensorEntity):
    """Info sensor showing static meter details (Address, Tariff, etc)."""

    def __init__(
        self,
        coordinator,
        meter_id: str,
        data_key: str,
        name: str,
        icon: str,
        device_info: DeviceInfo,
        device_class: str = None,
    ) -> None:
        """Initialize info sensor."""
        super().__init__(coordinator)

        self._meter_id = meter_id
        self._data_key = data_key

        # Entity attributes
        self._attr_name = name
        self._attr_unique_id = f"energa_{meter_id}_{data_key}_info"
        self._attr_has_entity_name = True
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_device_info = device_info

    @property
    def native_value(self):
        """Return the value from coordinator data."""
        if not self.coordinator.data:
            return None

        for meter in self.coordinator.data:
            if str(meter.get("meter_point_id")) == str(self._meter_id):
                return meter.get(self._data_key)
        return None
