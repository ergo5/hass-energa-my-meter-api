"""Sensor platform for Energa Mobile v3.6.0-beta.12."""
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

    entities = []
    meters_data = coordinator.data or []
    
    if not meters_data: return


    for meter in meters_data:
        meter_id = meter["meter_point_id"]

        for key, name, unit, dclass, sclass, icon, category in SENSOR_TYPES:
            entities.append(EnergaSensor(coordinator, meter_id, key, name, unit, dclass, sclass, icon, category))

    async_add_entities(entities)

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
            data = await self.api.async_get_data()
            # Self-Healing Check (v3.6.0-beta.5)
            self.hass.async_create_task(self._check_and_fix_history(data))
            return data
        
        # FIX: Dodana obsługa wygaśnięcia tokena
        except EnergaTokenExpiredError as err:
            _LOGGER.warning("Token Energa wygasł. Próbuję ponownego logowania.")
            try:
                await self.api.async_login()
                return await self.api.async_get_data()
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
        if self.coordinator.data:
            meter_data = next((m for m in self.coordinator.data if m["meter_point_id"] == self._meter_id), None)
            if meter_data:
                key_to_fetch = self._data_key
                # Mapowanie Nowych Sensorów na Total (Live) - FIX v3.5.17 (Smart Import alignment)
                if self._data_key == "import_total": key_to_fetch = "total_plus"
                elif self._data_key == "export_total": key_to_fetch = "total_minus"
                
                val = meter_data.get(key_to_fetch)
                if val is not None:
                    # ZERO-GUARD: Prevent meter reset detection if API returns 0 or glitch
                    f_val = float(val)
                    if f_val <= 0 and self._restored_value and float(self._restored_value) > 100:
                        _LOGGER.warning(f"Energa [{self._meter_id}]: Ignorowano błędny odczyt '0' (poprzedni: {self._restored_value}).")
                        return self._restored_value
                        
                    self._restored_value = val
                    return val

        if self._restored_value is not None:
            return self._restored_value
        return None

    @property
    def device_info(self) -> DeviceInfo:
        meter_data = next((m for m in self.coordinator.data if m["meter_point_id"] == self._meter_id), {}) if self.coordinator.data else {}
        ppe = meter_data.get("ppe", "Unknown")
        serial = meter_data.get("meter_serial", str(self._meter_id))
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._meter_id))},
            name=f"Licznik Energa {serial}",
            manufacturer="Energa-Operator",
            model=f"PPE: {ppe} | Licznik: {serial}",
            configuration_url="https://mojlicznik.energa-operator.pl",
            sw_version="3.6.0-beta.13",
        )