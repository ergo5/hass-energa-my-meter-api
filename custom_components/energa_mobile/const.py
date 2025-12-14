"""Constants for the Energa Mobile integration."""

DOMAIN = "energa_mobile"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

BASE_URL = "https://api-mojlicznik.energa-operator.pl/dp"
LOGIN_ENDPOINT = "/apihelper/UserLogin"
SESSION_ENDPOINT = "/apihelper/SessionStatus"
DATA_ENDPOINT = "/resources/user/data"
CHART_ENDPOINT = "/resources/mchart"

HEADERS = {
    "User-Agent": "Energa/3.1.2 (pl.energa-operator.mojlicznik; build:1; iOS 16.6.1) Alamofire/5.6.4",
    "Accept": "application/json",
    "Accept-Language": "pl-PL;q=1.0, en-PL;q=0.9",
    "Content-Type": "application/json"
}

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, EntityCategory

# Konfiguracja sensorów: (key, name, unit, device_class, state_class, icon, category)
SENSOR_TYPES = [
    ("import_total", "Energa Pobór – Licznik całkowity", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:transmission-tower", None),
    ("export_total", "Energa Produkcja – Licznik całkowity", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:solar-power", None),
    
    ("daily_pobor", "Energa Pobór Dziś", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:flash", None),
    ("daily_produkcja", "Energa Produkcja Dziś", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:solar-power", None),

    ("total_plus", "Stan Licznika - Pobór", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:counter", None),
    ("total_minus", "Stan Licznika - Produkcja", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:counter", None),

    ("tariff", "Taryfa", None, None, None, "mdi:information-outline", EntityCategory.DIAGNOSTIC),
    ("ppe", "PPE", None, None, None, "mdi:barcode", EntityCategory.DIAGNOSTIC),
    ("meter_serial", "Numer licznika", None, None, None, "mdi:counter", EntityCategory.DIAGNOSTIC),
    ("address", "Adres", None, None, None, "mdi:map-marker", EntityCategory.DIAGNOSTIC),
    ("contract_date", "Data umowy", None, SensorDeviceClass.DATE, None, "mdi:calendar-check", EntityCategory.DIAGNOSTIC),
]