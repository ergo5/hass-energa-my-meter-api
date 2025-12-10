from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from .const import DOMAIN

async def async_setup_entry(hass, entry, add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        EnergaTotalSensor(coord, "total_aplus", "Energa Total A+", ENERGY_KILO_WATT_HOUR),
        EnergaTotalSensor(coord, "total_aminus", "Energa Total A-", ENERGY_KILO_WATT_HOUR),
        EnergaListSensor(coord, "hourly_aplus", "Energa Hourly A+", ENERGY_KILO_WATT_HOUR),
        EnergaListSensor(coord, "hourly_aminus", "Energa Hourly A-", ENERGY_KILO_WATT_HOUR),
    ]

    add_entities(sensors)

class EnergaBase(SensorEntity):
    def __init__(self, coord, key, name, unit):
        self.coordinator = coord
        self._attr_name = name
        self._key = key
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self):
        return self.coordinator.data[self._key]

    async def async_update(self):
        await self.coordinator.async_request_refresh()

class EnergaTotalSensor(EnergaBase):
    pass

class EnergaListSensor(EnergaBase):
    pass
