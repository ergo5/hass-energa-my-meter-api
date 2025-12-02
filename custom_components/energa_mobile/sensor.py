"""Sensors for Energa Mobile."""
from datetime import timedelta
import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
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
        update_interval=timedelta(hours=1), # Odświeżanie co godzinę
    )

    await coordinator.async_config_entry_first_refresh()

    entities = [
        EnergaSensor(coordinator, "pobor", "Energa Pobór (Import)"),
        EnergaSensor(coordinator, "produkcja", "Energa Produkcja (Eksport)"),
    ]
    
    async_add_entities(entities)

class EnergaSensor(CoordinatorEntity, SensorEntity):
    """Sensor Energa."""

    def __init__(self, coordinator, data_key, name):
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{data_key}"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get(self._data_key)
        return None