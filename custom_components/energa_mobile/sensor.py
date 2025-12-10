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
from homeassistant.helpers.entity import DeviceInfo
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
        # --- DO PANELU ENERGII (Liczniki dzienne - resetują się o północy) ---
        (
            "daily_pobor", 
            "Energa Pobór (Dziś)", 
            UnitOfEnergy.KILO_WATT_HOUR, 
            SensorDeviceClass.ENERGY, 
            SensorStateClass.TOTAL_INCREASING, # Kluczowe dla resetu o północy!
            "mdi:home-lightning-bolt"
        ), 
        (
            "daily_produkcja", 
            "Energa Produkcja (Dziś)", 
            UnitOfEnergy.KILO_WATT_HOUR, 
            SensorDeviceClass.ENERGY, 
            SensorStateClass.TOTAL_INCREASING, # Kluczowe dla resetu o północy!
            "mdi:solar-power-variant"
        ),
        
        # --- STANY LICZNIKA (Informacyjne) ---
        ("total_plus", "Energa Stan Licznika (Pobór)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:transmission-tower-export"),
        ("total_minus", "Energa Stan Licznika (Produkcja)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:transmission-tower-import"),
        
        # --- DIAGNOSTYKA ---
        ("tariff", "Taryfa", None, None, None, "mdi:file-document-outline"),
        ("ppe", "PPE", None, None, None, "mdi:barcode"),
        ("address", "Adres", None, None, None, "mdi:map-marker"),
    ]

    entities = []
    for key, name, unit, dev_class, state_class, icon in sensors:
        entities.append(EnergaSensor(coordinator, key, name, unit, dev_class, state_class, icon))
    
    async_add_entities(entities)

class EnergaSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, data_key, name, unit, dev_class, state_class, icon):
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_name = name
        self._attr_unique_id = f"energa_{data_key}_{coordinator.config_entry.entry_id}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        
        if "tariff" in data_key or "ppe" in data_key or "address" in data_key:
             self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self.coordinator.data.get(self._data_key)

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data or {}
        meter_id = data.get("meter_point_id", "Nieznany")
        ppe = data.get("ppe", "Nieznany")
        
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=f"Licznik Energa {meter_id}",
            manufacturer="Energa-Operator",
            model=f"PPE: {ppe}",
            configuration_url="https://mojlicznik.energa-operator.pl",
            sw_version="2.2.0 (OBIS Auto-Detect)"
        )