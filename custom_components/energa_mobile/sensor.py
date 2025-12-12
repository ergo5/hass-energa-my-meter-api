"""Sensors for Energa Mobile v3.5.5."""
from datetime import timedelta
import logging
import asyncio # <--- DODANY IMPORT ASYNCIO
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
    UpdateFailed,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from .api import EnergaAuthError, EnergaConnectionError, EnergaTokenExpiredError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    api = hass.data[DOMAIN][entry.entry_id]

    coordinator = EnergaDataCoordinator(hass, api)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        _LOGGER.warning("Energa: Start bez pełnych danych API")

    entities = []
    meters = coordinator.data or []
    if not meters:
        return

    for meter in meters:
        meter_id = meter["meter_point_id"]

        sensors = [
            # NOWE, CZYSTE SENSORY DO PANELU ENERGII
            ("import_total", "Energa Pobór – Licznik całkowity", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:transmission-tower"),
            ("export_total", "Energa Produkcja – Licznik całkowity", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:solar-power"),
            
            # Liczniki Total (Odczyt z API - Twoje "święte" liczniki)
            ("total_plus", "Stan Licznika - Pobór", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:counter"),
            ("total_minus", "Stan Licznika - Produkcja", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:counter"),

            # Info sensors
            ("tariff", "Taryfa", None, None, None, "mdi:information-outline"),
            ("ppe", "PPE", None, None, None, "mdi:barcode"),
            ("meter_serial", "Numer licznika", None, None, None, "mdi:counter"),
        ]

        for key, name, unit, dclass, sclass, icon in sensors:
            entities.append(
                EnergaSensor(
                    coordinator,
                    meter_id,
                    key,
                    name,
                    unit,
                    dclass,
                    sclass,
                    icon,
                )
            )

    async_add_entities(entities)

class EnergaDataCoordinator(DataUpdateCoordinator):
    """Live API polling."""

    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="Energa Mobile Live API",
            update_interval=timedelta(hours=1),
        )
        self.api = api
        self._errors = 0

    async def _async_update_data(self):
        try:
            data = await self.api.async_get_data()

            if self._errors > 0:
                _LOGGER.info("Energa API: przywrócono połączenie")
                self._errors = 0
                self.update_interval = timedelta(hours=1)

            return data
        
        # DODANO EnergaTokenExpiredError do obsługi 401/403 z API
        except (EnergaConnectionError, asyncio.TimeoutError, EnergaTokenExpiredError) as err:
            self._errors += 1
            delay = 15 if self._errors > 2 else (5 if self._errors > 1 else 2)
            self.update_interval = timedelta(minutes=delay)
            
            # Jeśli to problem z tokenem (401/403), spróbujemy się ponownie zalogować
            if isinstance(err, EnergaTokenExpiredError):
                _LOGGER.warning("Energa Token wygasł. Spróbuję ponownego logowania.")
                try:
                    await self.api.async_login()
                except Exception:
                    pass # Jeśli logowanie padnie, rzucimy UpdateFailed
            
            # Jeśli login się nie powiódł, rzucamy UpdateFailed i Coordinator będzie retryował
            raise UpdateFailed(f"API ERROR: {err}") from err

        except EnergaAuthError as err:
            self.update_interval = timedelta(hours=1)
            raise UpdateFailed(f"Błąd autoryzacji Energa: {err}") from err

class EnergaSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    # ... (klasa EnergaSensor pozostaje bez zmian, używając RestoreEntity) ...
    def __init__(
        self,
        coordinator,
        meter_id,
        key,
        name,
        unit,
        device_class,
        state_class,
        icon,
    ):
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._data_key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._restored_value = None
        
        self._attr_unique_id = f"energa_{key}_{meter_id}"

        if unit is None:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            
    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._restored_value = float(last_state.state)
            except ValueError:
                self._restored_value = None

    @property
    def native_value(self):
        """Return sensor state from live API or restored state."""

        data = self.coordinator.data
        if data:
            meter = next(
                (m for m in data if m["meter_point_id"] == self._meter_id),
                None,
            )
            if meter:
                # Mapowanie dla czystych sensorów total_increasing na total_plus/minus
                live_map = {
                    "import_total": "total_plus",
                    "export_total": "total_minus",
                }
                
                key_to_fetch = live_map.get(self._data_key, self._data_key)
                
                value = meter.get(key_to_fetch)
                if isinstance(value, (int, float)):
                    self._restored_value = float(value)
                    return self._restored_value
        
        if self._restored_value is not None:
            return self._restored_value
        
        return None

    @property
    def device_info(self) -> DeviceInfo:
        meter = (
            next(
                (m for m in self.coordinator.data if m["meter_point_id"] == self._meter_id),
                None,
            )
            or {}
        )

        return DeviceInfo(
            identifiers={(DOMAIN, str(self._meter_id))},
            name=f"Licznik Energa {meter.get('meter_serial','')}",
            manufacturer="Energa-Operator",
            model=f"PPE {meter.get('ppe','')}",
            configuration_url="https://mojlicznik.energa-operator.pl",
            sw_version="3.5.5",
        )