from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, add):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    device = DeviceInfo(
        identifiers={(DOMAIN, coordinator.meterpoint)},
        name=f"Licznik Energa {coordinator.meterpoint}",
        manufacturer="Energa Operator",
        model=coordinator.meter_id,
    )

    add([
        EnergaTotal(coordinator, "total_aplus", "TOTAL Pobór A+", "mdi:flash", "aplus", device),
        EnergaTotal(coordinator, "total_aminus", "TOTAL Produkcja A-", "mdi:solar-power", "aminus", device),
        EnergaHourly(coordinator, "hourly_aplus", "HOURLY Pobór A+", "mdi:flash", "h_aplus", device),
        EnergaHourly(coordinator, "hourly_aminus", "HOURLY Produkcja A-", "mdi:solar-power", "h_aminus", device),
    ])

class EnergaBase(CoordinatorEntity, SensorEntity):
    def __init__(self, coord, uid, name, icon, field, device):
        super().__init__(coord)
        self._attr_unique_id = f"{coord.meterpoint}_{uid}"
        self._attr_name = name
        self._attr_icon = icon
        self.field = field
        self._attr_device_info = device

    @property
    def native_unit_of_measurement(self):
        return "kWh"

class EnergaTotal(EnergaBase):
    @property
    def native_value(self):
        return self.coordinator.data["total"].get(self.field)

class EnergaHourly(EnergaBase):
    @property
    def native_value(self):
        return self.coordinator.data["hourly"].get(self.field)
