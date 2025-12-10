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
        # Totale
        ("total_plus", "Energa Import Total", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        ("total_minus", "Energa Export Total", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        # Dzienne
        ("daily_pobor", "Energa Import Dziś", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING), 
        ("daily_produkcja", "Energa Export Dziś", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        # Info
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
        
        if "tariff" in data_key or "ppe" in data_key or "address" in data_key:
             self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self.coordinator.data.get(self._data_key)