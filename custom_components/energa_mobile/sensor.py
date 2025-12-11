"""Sensors for Energa Mobile v2.9.5 (Pro Energy Panel Names)."""
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
from .api import EnergaAuthError, EnergaConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    api = hass.data[DOMAIN][entry.entry_id]
    coordinator = EnergaDataCoordinator(hass, api)
    
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        _LOGGER.warning("Energa: Start bez pełnych danych.")

    entities = []
    meters_data = coordinator.data or []
    if not meters_data: return

    for meter in meters_data:
        meter_id = meter["meter_point_id"]
        
        sensors_config = [
            # Standardowe sensory (pomocnicze)
            ("daily_pobor", "Pobór (Dziś)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:home-lightning-bolt"), 
            ("daily_produkcja", "Produkcja (Dziś)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:solar-power-variant"),
            ("tariff", "Taryfa", None, None, None, "mdi:file-document-outline"),
            ("ppe", "Numer PPE", None, None, None, "mdi:barcode"),
            ("meter_serial", "Numer Licznika", None, None, None, "mdi:counter"),
            ("address", "Adres", None, None, None, "mdi:map-marker"),
            ("contract_date", "Data Umowy", None, SensorDeviceClass.DATE, None, "mdi:calendar-check"),
            
            # --- SENSORY DLA PANELU ENERGII ---
            # ID: consumption_energy_panel -> "Panel Energii - Pobór"
            ("consumption_energy_panel", "Panel Energii - Pobór", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:transmission-tower-export"),
            # ID: production_energy_panel -> "Panel Energii - Produkcja"
            ("production_energy_panel", "Panel Energii - Produkcja", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:transmission-tower-import"),
        ]

        for key, name, unit, dev_class, state_class, icon in sensors_config:
            entities.append(EnergaSensor(coordinator, meter_id, key, name, unit, dev_class, state_class, icon))
    
    async_add_entities(entities)

class EnergaDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(hass, _LOGGER, name="Energa Mobile Coordinator", update_interval=timedelta(hours=1))
        self.api = api
        self._error_count = 0

    async def _async_update_data(self):
        try:
            data = await self.api.async_get_data()
            if self._error_count > 0:
                _LOGGER.info("Energa: Połączenie przywrócone.")
                self._error_count = 0
                self.update_interval = timedelta(hours=1)
            return data
        except (EnergaConnectionError, asyncio.TimeoutError) as err:
            self._error_count += 1
            retry_delay = 15 if self._error_count > 2 else (5 if self._error_count > 1 else 2)
            self.update_interval = timedelta(minutes=retry_delay)
            raise UpdateFailed(f"Błąd komunikacji: {err}") from err
        except EnergaAuthError as err:
            self.update_interval = timedelta(hours=1)
            raise UpdateFailed(f"Błąd autoryzacji: {err}") from err

class EnergaSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, meter_id, data_key, name, unit, dev_class, state_class, icon):
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._data_key = data_key
        self._attr_name = name
        self._attr_unique_id = f"energa_{data_key}_{meter_id}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        if unit != UnitOfEnergy.KILO_WATT_HOUR: 
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        if self.coordinator.data:
            meter_data = next((m for m in self.coordinator.data if m["meter_point_id"] == self._meter_id), None)
            if meter_data:
                # Mapowanie dla sensorów panelowych (aby Live pokazywały stan licznika)
                key_to_fetch = self._data_key
                if self._data_key == "consumption_energy_panel":
                    key_to_fetch = "total_plus"
                elif self._data_key == "production_energy_panel":
                    key_to_fetch = "total_minus"

                val = meter_data.get(key_to_fetch)
                if val is None and self._attr_device_class == SensorDeviceClass.ENERGY: return 0.0
                return val
        if self._attr_device_class == SensorDeviceClass.ENERGY: return 0.0
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
            sw_version="2.9.5"
        )