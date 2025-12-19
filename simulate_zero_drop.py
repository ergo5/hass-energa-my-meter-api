
import asyncio
from unittest.mock import MagicMock
from custom_components.energa_mobile.api import EnergaAPI
from custom_components.energa_mobile.sensor import EnergaSensor, EnergaDataCoordinator
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass

# Mock Hass
class MockHass:
    def __init__(self):
        self.data = {}
        self.bus = MagicMock()
        self.states = MagicMock()
        self.config_entries = MagicMock()

async def test_zero_drop_scenario():
    print("--- Simulating Zero Drop (Missing API Data) ---")
    
    # 1. Setup Mock API with NO data (None defaults)
    api = EnergaAPI("test", "test", MagicMock())
    # We simulate what async_get_data returns when fetch_all_meters finds no measurements
    # The new code in api.py should init these as None
    
    BAD_DATA_FROM_API = [{
        "meter_point_id": "12345678",
        "ppe": "PL000000",
        "meter_serial": "123",
        "total_plus": None,   # <--- THIS IS KEY. Previously 0.0
        "total_minus": None,
        "daily_pobor": None,
        "daily_produkcja": None
    }]
    
    api.async_get_data = MagicMock(return_value=asyncio.Future())
    api.async_get_data.return_value.set_result(BAD_DATA_FROM_API)
    
    hass = MockHass()
    coordinator = EnergaDataCoordinator(hass, api)
    coordinator.data = BAD_DATA_FROM_API
    
    # 2. Setup Sensor
    sensor_imp = EnergaSensor(
        coordinator, "12345678", "total_plus", "Import", 
        "kWh", "energy", "total_increasing", "mdi:flash", "diagnostic"
    )
    
    # Simulate restored state (e.g. 24000 kWh from yesterday)
    sensor_imp._restored_value = 24000.0
    
    # 3. Check Native Value
    val = sensor_imp.native_value
    print(f"API Value: None")
    print(f"Restored Value: {sensor_imp._restored_value}")
    print(f"Resulting Sensor Value: {val}")
    
    if val == 0.0:
        print("FAIL: Sensor returned 0.0! This will cause a spike.")
    elif val == 24000.0:
        print("SUCCESS: Sensor used restored value (or None) safely.")
    elif val is None:
        print("SUCCESS: Sensor returned None (Unavailable). Safe.")
    else:
        print(f"UNKNOWN: {val}")

    # 4. Verify Export as well
    sensor_exp = EnergaSensor(
        coordinator, "12345678", "total_minus", "Export", 
        "kWh", "energy", "total_increasing", "mdi:flash", "diagnostic"
    )
    sensor_exp._restored_value = 5000.0
    val_exp = sensor_exp.native_value
    
    if val_exp == 0.0:
        print("FAIL: Export Sensor returned 0.0!")
    else:
        print(f"SUCCESS: Export Sensor returned {val_exp}.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_zero_drop_scenario())
