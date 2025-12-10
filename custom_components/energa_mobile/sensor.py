"""Sensors for Energa Mobile."""
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
    CoordinatorEntity, DataUpdateCoordinator,
)
from homeassistant.helpers.entity import DeviceInfo  # <--- WAŻNY IMPORT
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    api = hass.data[DOMAIN][entry.entry_id]
    
    coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name="energa_mobile_coordinator",
        update_method=api.async_get_data, update_interval=timedelta(hours=1),
    )
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        # Liczniki Całkowite (Totals)
        ("total_plus", "Energa Import Total", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        ("total_minus", "Energa Export Total", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        
        # Liczniki Dzienne (Obliczane z wykresu godzinowego)
        ("daily_pobor", "Energa Import Dziś", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING), 
        ("daily_produkcja", "Energa Export Dziś", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        
        # Diagnostyka
        ("tariff", "Taryfa", None, None, None),
        ("ppe", "PPE", None, None, None),
        ("address", "Adres", None, None, None),
    ]

    entities = []
    for key, name, unit, dev_class, state_class in sensors:
        entities.append(EnergaSensor(coordinator, key, name, unit, dev_class, state_class))
    
    async_add_entities(entities)

class EnergaSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, data_key, name, unit, dev_class, state_class):
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_name = name
        self._attr_unique_id = f"energa_{data_key}_{coordinator.config_entry.entry_id}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class
        
        # Ustawiamy kategorię diagnostyczną dla informacji tekstowych
        if "tariff" in data_key or "ppe" in data_key or "address" in data_key:
             self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Zwraca wartość sensora."""
        return self.coordinator.data.get(self._data_key)

    @property
    def device_info(self) -> DeviceInfo:
        """Definicja urządzenia w Home Assistant."""
        # Pobieramy dane do opisu urządzenia z API
        data = self.coordinator.data or {}
        meter_id = data.get("meter_point_id", "Nieznany")
        ppe = data.get("ppe", "Nieznany")
        
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=f"Licznik Energa {meter_id}",
            manufacturer="Energa-Operator",
            model=f"PPE: {ppe}",
            configuration_url="https://mojlicznik.energa-operator.pl",
            sw_version="2.0.0 (OBIS Auto-Detect)"
        )