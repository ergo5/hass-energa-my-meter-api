"""Sensors for Energa Mobile."""
from datetime import timedelta
import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Setup sensorów."""
    api = hass.data[DOMAIN][entry.entry_id]

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="energa_mobile_coordinator",
        update_method=api.async_get_data,
        update_interval=timedelta(hours=6), 
    )

    await coordinator.async_config_entry_first_refresh()

    # Definicja wszystkich dostępnych sensorów
    sensors_config = [
        # Główne sensory (Total Increasing) - dane z lastMeasurements
        ("pobor", "Energa Pobór (Import) Total", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, None),
        ("produkcja", "Energa Produkcja (Eksport) Total", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, None),
        
        # Nowe sensory DZIENNE (Zużycie DZIŚ) - Klasa stanu musi być NONE, by uniknąć błędu HA
        ("daily_pobor", "Energa Pobór Dziś", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, None, None), # FIX: state_class zmieniony na None
        ("daily_produkcja", "Energa Produkcja Dziś", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, None, None), # FIX: state_class zmieniony na None
        
        # Sensory diagnostyczne
        ("tariff", "Taryfa", None, None, None, EntityCategory.DIAGNOSTIC),
        ("address", "Adres PPE", None, None, None, EntityCategory.DIAGNOSTIC),
        ("seller", "Sprzedawca", None, None, None, EntityCategory.DIAGNOSTIC),
        ("contract_date", "Data umowy", None, None, None, EntityCategory.DIAGNOSTIC),
        ("ppe", "Numer Licznika", None, None, None, EntityCategory.DIAGNOSTIC),
    ]

    entities = []
    for key, name, unit, dev_class, state_class, category in sensors_config:
        if coordinator.data.get(key) is not None or key.startswith("daily_"):
            entities.append(EnergaSensor(coordinator, key, name, unit, dev_class, state_class, category))
    
    async_add_entities(entities)

class EnergaSensor(CoordinatorEntity, SensorEntity):
    """Sensor Energa."""

    def __init__(self, coordinator, data_key, name, unit, dev_class, state_class, category):
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_name = name
        self._attr_unique_id = f"energa_{data_key}_{coordinator.config_entry.entry_id}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class
        self._attr_entity_category = category
        
        if "pobor" in data_key: self._attr_icon = "mdi:transmission-tower-import"
        elif "produkcja" in data_key: self._attr_icon = "mdi:solar-power"
        elif "tariff" in data_key: self._attr_icon = "mdi:file-document-outline"
        elif "address" in data_key: self._attr_icon = "mdi:map-marker"
        elif "seller" in data_key: self._attr_icon = "mdi:account-tie"

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get(self._data_key)
        return None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": "Energa Licznik",
            "manufacturer": "Energa Operator",
            "model": "Mobile API",
            "sw_version": "1.2.4", # AKTUALIZACJA WERSJI
        }