"""Sensor platform for Energa Mobile v3.7.0-dev."""
from datetime import timedelta, datetime
import logging
from homeassistant.components.sensor import (
    SensorEntity, SensorDeviceClass, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
)
from homeassistant.loader import async_get_integration
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

# FIX: Dodajemy obsługę błędu wygaśnięcia tokena
from .api import EnergaAuthError, EnergaConnectionError, EnergaTokenExpiredError 
from .const import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    api = hass.data[DOMAIN][entry.entry_id]
    coordinator = EnergaDataCoordinator(hass, api)
    try: await coordinator.async_config_entry_first_refresh()
    except Exception: _LOGGER.warning("Energa: Start bez pełnych danych.")

    # FIX: Dynamic version fetching
    integration = await async_get_integration(hass, DOMAIN)
    sw_version = integration.version

    # NEW v3.7: coordinator.data is now {live: [...], hourly_stats: {...}}
    #meters_data = coordinator.data.get("live", []) if coordinator.data else []
    
    if not coordinator.data or not coordinator.data.get("live"):
        _LOGGER.warning("No meter data available at startup")
        return

    meters_data = coordinator.data["live"]
    
    # SPLIT: Create live sensors (visible, for diagnostics)
    live_sensors = _create_live_sensors(coordinator, meters_data, sw_version)
    
    # SPLIT: Create statistics sensors (invisible, for Energy Dashboard)
    stats_sensors = _create_statistics_sensors(coordinator, meters_data, sw_version)
    
    _LOGGER.info(
        f"Created {len(live_sensors)} live sensors and {len(stats_sensors)} statistics sensors"
    )
    
    async_add_entities(live_sensors + stats_sensors)


def _create_live_sensors(coordinator, meters_data, sw_version):
    """Create live state sensors (visible in UI, for diagnostics)."""
    sensors = []
    
    for meter in meters_data:
        meter_id = meter["meter_point_id"]
        for key, name, unit, dclass, sclass, icon, category in SENSOR_TYPES:
            sensors.append(
                EnergaSensor(
                    coordinator, meter_id, key, name, unit, 
                    dclass, sclass, icon, category, sw_version
                )
            )
    
    return sensors


def _create_statistics_sensors(coordinator, meters_data, sw_version):
    """Create invisible statistics sensors (Energy Dashboard only)."""
    from .statistics_sensor import EnergaStatisticsSensor
    from homeassistant.helpers.device_registry import DeviceInfo
    
    sensors = []
    
    for meter in meters_data:
        meter_id = meter["meter_point_id"]
        ppe = meter.get("ppe", meter_id)
        serial = meter.get("meter_serial", meter_id)
        
        # Device info (same as live sensors)
        device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"Energa Mobile {serial}",
            manufacturer="Energa-Operator",
            model=f"PPE: {ppe} | Licznik: {serial}",
            configuration_url="https://mojlicznik.energa-operator.pl",
            sw_version=sw_version,
        )
        
        # Create statistics sensors (PANEL prominent naming)
        sensors.append(
            EnergaStatisticsSensor(
                coordinator, meter_id, "import", 
                "Energa Panel Import",  # PANEL in name
                device_info
            )
        )
        sensors.append(
            EnergaStatisticsSensor(
                coordinator, meter_id, "export", 
                "Energa Panel Export",
                device_info
            )
        )
    
    return sensors


class EnergaDataCoordinator(DataUpdateCoordinator):
    """Koordynator aktualizacji danych."""

    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="Energa Mobile API",
            update_interval=timedelta(minutes=30),
        )
        self.api = api
        self._last_repair_attempt = {} # Circuit Breaker state

    async def _async_update_data(self):
        try:
            # Fetch live meter data (meterPoints endpoint)
            live_data = await self.api.async_get_data()
            
            # NEW v3.7: Fetch hourly statistics (mainChart endpoint)
            # This powers the invisible statistics sensors for Energy Dashboard
            hourly_stats = {}
            for meter in live_data:
                meter_id = meter["meter_point_id"]
                try:
                    hourly_stats[meter_id] = await self.api.async_get_hourly_statistics(
                        meter_id, days_back=2  # Last 48 hours
                    )
                    _LOGGER.debug(
                        f"Fetched hourly stats for {meter_id}: "
                        f"{len(hourly_stats[meter_id].get('import', []))} import points, "
                        f"{len(hourly_stats[meter_id].get('export', []))} export points"
                    )
                except Exception as e:
                    _LOGGER.error(f"Failed to fetch hourly stats for {meter_id}: {e}")
                    hourly_stats[meter_id] = {"import": [], "export": []}
            
            # Return combined data structure
            result = {
                "live": live_data,  # For live sensors (total, daily, tariff, etc.)
                "hourly_stats": hourly_stats  # For statistics sensors
            }
            
            # Self-Healing Check (v3.6.0-beta.5) - operates on live data
            self.hass.async_create_task(self._check_and_fix_history(live_data))
            
            return result
        
        # FIX: Dodana obsługa wygaśnięcia tokena
        except EnergaTokenExpiredError as err:
            _LOGGER.warning("Token Energa wygasł. Próbuję ponownego logowania.")
            try:
                await self.api.async_login()
                return await self._async_update_data()  # Retry entire fetch
            except EnergaAuthError:
                raise UpdateFailed(f"Błąd autoryzacji Energa po wygaśnięciu tokena: {err}") from err
            except EnergaConnectionError:
                raise UpdateFailed(f"Błąd połączenia Energa po wygaśnięciu tokena: {err}") from err
        
        except EnergaConnectionError as err:
            raise UpdateFailed(f"Błąd połączenia Energa: {err}") from err
        
        except EnergaAuthError as err:
            raise UpdateFailed(f"Błąd autoryzacji Energa: {err}") from err
        
        except Exception as err:
            raise UpdateFailed(f"Nieznany błąd Energa: {err}") from err

    def get_hourly_statistics(self, meter_id: str, data_key: str):
        """Get hourly statistics for a specific meter and data key.
        
        Args:
            meter_id: Meter point ID
            data_key: "import" or "export"
            
        Returns:
            List of StatisticData dicts with "start" and "sum" keys
        """
        if not self.data:
            return []
        
        hourly_stats = self.data.get("hourly_stats", {})
        meter_stats = hourly_stats.get(meter_id, {})
        return meter_stats.get(data_key, [])

    async def _check_and_fix_history(self, meters_data):
        """Self-healing: wykrywanie dziur w historii i autonaprawa."""
        if not meters_data: return

        # Import locally to avoid circular dependency
        from homeassistant.helpers import entity_registry as er
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import get_last_statistics
        from homeassistant.util import dt as dt_util
        from . import run_history_import

        try:
            ent_reg = er.async_get(self.hass)
            
            for meter in meters_data:
                meter_id = meter["meter_point_id"]
                # Sprawdzamy główny sensor importu (v3/Total)
                uid = f"energa_import_total_{meter_id}_v3"
                entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
                
                if not entity_id: continue

                # Sprawdź kiedy był ostatni wpis w statistykach
                last_stats = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, entity_id, True, {"start"}
                )
                
                start_date = None
                
                if not last_stats:
                    # Brak historii - może nowa instalacja? Pobierz 7 dni wstecz dla bezpieczeństwa.
                    # Ale tylko jeśli sensor w ogóle istnieje w rejestrze (a istnieje, bo przeszło check wyżej)
                    _LOGGER.info(f"Self-Healing: Brak statystyk dla {entity_id}. Inicjalizacja historii (7 dni).")
                    start_date = dt_util.now() - timedelta(days=7)
                else:
                    stat = last_stats[entity_id][0]
                    last_dt = datetime.fromtimestamp(stat["start"], tz=dt_util.UTC)
                    diff = dt_util.now() - last_dt
                    
                    # Jeśli dziura większa niż 3h (Energa ma opóźnienie, ale chcemy być na bieżąco)
                    if diff > timedelta(hours=3):
                        # CIRCUIT BREAKER v3.6.0-beta.8
                        last_try = self._last_repair_attempt.get(meter_id)
                        if last_try and (dt_util.now() - last_try) < timedelta(hours=4):
                             _LOGGER.info(f"Self-Healing: Wstrzymano naprawę dla {meter_id} (Cool-down do {last_try + timedelta(hours=4)}).")
                             start_date = None # Skip
                        else:
                             _LOGGER.debug(f"Self-Healing: Wykryto opóźnienie danych ({diff}). Sprawdzam aktualizacje.")
                             start_date = last_dt

                if start_date:
                     # Pobieramy od wykrytej daty AŻ DO DZISIAJ (żeby zachować ciągłość anchor)
                     days_to_fetch = (dt_util.now().date() - start_date.date()).days + 2
                     if days_to_fetch > 0:
                        # Uruchom import w tle
                        self._last_repair_attempt[meter_id] = dt_util.now() # Mark attempt
                        self.hass.async_create_task(
                            run_history_import(self.hass, self.api, meter, start_date, days_to_fetch)
                        )

        except Exception as e:
            _LOGGER.error(f"Self-Healing Error: {e}")


class EnergaSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Instancja sensora."""

    def __init__(
        self,
        coordinator,
        meter_id,
        key,
        name,
        unit,
        device_class,
        state_class,
        icon,
        category,
        sw_version,
    ):
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._data_key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_entity_category = category 
        self._restored_value = None
        self._sw_version = sw_version
        
        # NUCLEAR OPTION v3 - Force fresh entities to clear history spikes
        # v3.5.23: Switched to _v3 suffix
        if key in ["import_total", "export_total"]:
            self._attr_unique_id = f"energa_{key}_{meter_id}_v3"
        else:
            self._attr_unique_id = f"energa_{key}_{meter_id}"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._restored_value = float(last_state.state)
            except ValueError:
                self._restored_value = None

    @property
    def native_value(self):
        """Zwraca stan sensora z API lub przywrócony stan."""
        # NEW v3.7: coordinator.data is now {live: [...], hourly_stats: {...}}
        if self.coordinator.data and self.coordinator.data.get("live"):
            meter_data = next(
                (m for m in self.coordinator.data["live"] if m["meter_point_id"] == self._meter_id), 
                None
            )
            if meter_data:
                val = meter_data.get(self._data_key)
                if val is not None:
                    # ZERO-GUARD: Prevent meter reset detection if API returns 0 or glitch
                    try:
                        f_val = float(val)
                        
                        # STRICT ZERO GUARD (v3.6.0-beta.18) - Modified for beta.19
                        # Only apply strict guard to LIFETIME counters (total_plus/total_minus).
                        # Daily sensors (daily_pobor) can validly be 0.
                        is_lifetime = self._data_key in ["total_plus", "total_minus", "import_total", "export_total"]
                        
                        if is_lifetime and f_val <= 0:
                            if self._restored_value and float(self._restored_value) > 100:
                                _LOGGER.error(f"Energa [{self._meter_id}]: Ignorowano '0' (poprzedni: {self._restored_value}).")
                                return self._restored_value
                            else:
                                _LOGGER.warning(f"Energa [{self._meter_id}]: Ignorowano '0' na starcie (Lifetime).")
                                return None
                    except (ValueError, TypeError):
                        pass # Not a number, skip guard

                    self._restored_value = val
                    return val


        if self._restored_value is not None:
            return self._restored_value
        return None

    @property
    def native_unit_of_measurement(self):
        """Jednostka."""
        return self._attr_native_unit_of_measurement

    @property
    def device_info(self):
        """Informacje o urządzeniu."""
        # FIX v3.6.0-beta.16: Correctly fetch PPE from API data, don't use internal ID
        ppe = self._meter_id
        serial = self._meter_id
        
        if self.coordinator.data and self.coordinator.data.get("live"):
             # Find data for this meter safely from "live" data
            meter_data = next((m for m in self.coordinator.data["live"] if m.get("meter_point_id") == self._meter_id), None)
            if meter_data:
                ppe = meter_data.get("ppe", self._meter_id)
                serial = meter_data.get("meter_serial", self._meter_id)
        
        return DeviceInfo(
            identifiers={("energa_mobile", serial)},
            name=f"Energa Mobile {serial}",
            manufacturer="Energa-Operator",
            model=f"PPE: {ppe} | Licznik: {serial}",
            configuration_url="https://mojlicznik.energa-operator.pl",
            sw_version=str(self._sw_version),  # Ensure string for AwesomeVersion compatibility
        )