"""Sensors for Energa Mobile v2.8.7."""
from datetime import timedelta, datetime
import logging
import asyncio
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo
from .api import EnergaAuthError, EnergaConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    api = hass.data[DOMAIN][entry.entry_id]
    coordinator = EnergaDataCoordinator(hass, api)
    try: await coordinator.async_config_entry_first_refresh()
    except Exception: _LOGGER.warning("Energa: Start bez danych (oczekiwanie na API).")

    sensors = [
        ("daily_pobor", "Energa Pobór (Dziś)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:home-lightning-bolt"), 
        ("daily_produkcja", "Energa Produkcja (Dziś)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:solar-power-variant"),
        ("total_plus", "Energa Stan Licznika (Pobór)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:transmission-tower-export"),
        ("total_minus", "Energa Stan Licznika (Produkcja)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:transmission-tower-import"),
        ("tariff", "Taryfa", None, None, None, "mdi:file-document-outline"),
        ("ppe", "PPE", None, None, None, "mdi:barcode"),
        ("meter_serial", "Numer Licznika", None, None, None, "mdi:counter"), # Nowy
        ("address", "Adres", None, None, None, "mdi:map-marker"),
        ("contract_date", "Data Umowy", None, SensorDeviceClass.DATE, None, "mdi:calendar-check"),
    ]
    entities = []
    for key, name, unit, dev_class, state_class, icon in sensors:
        entities.append(EnergaSensor(coordinator, key, name, unit, dev_class, state_class, icon))
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
    def __init__(self, coordinator, data_key, name, unit, dev_class, state_class, icon):
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_name = name
        self._attr_unique_id = f"energa_{data_key}_{coordinator.config_entry.entry_id}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        if unit != UnitOfEnergy.KILO_WATT_HOUR: self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        if self.coordinator.data:
            val = self.coordinator.data.get(self._data_key)
            if val is None and self._attr_device_class == SensorDeviceClass.ENERGY: return 0.0
            return val
        if self._attr_device_class == SensorDeviceClass.ENERGY: return 0.0
        return None

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data or {}
        meter_id = data.get("meter_point_id", "Unknown")
        ppe = data.get("ppe", "Unknown")
        serial = data.get("meter_serial", "")
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=f"Licznik Energa {serial if serial else meter_id}",
            manufacturer="Energa-Operator",
            model=f"PPE: {ppe} | Licznik: {serial}", # W polu Model
            configuration_url="https://mojlicznik.energa-operator.pl",
            sw_version="2.8.7"
        )