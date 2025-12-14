"""Sensors for Energa Mobile v3.5.17."""
from datetime import timedelta
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
            update_interval=timedelta(hours=1),
        )
        self.api = api

    async def _async_update_data(self):
        try:
            return await self.api.async_get_data()
        
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
        self._attr_entity_category = category # FIX: Użycie kategorii
        self._restored_value = None
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
            sw_version="3.5.17",
        )