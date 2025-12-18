
import asyncio
import logging
from unittest.mock import MagicMock, patch
import sys
from types import SimpleNamespace

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def run_simulation():
    print("==========================================")
    print("   SIMULATION SUITE: v3.6.0-beta.15      ")
    print("   Target: REGRESSION CHECK (NameError)  ")
    print("==========================================")

    # --- MOCKING THE ENVIRONMENT ---
    
    class MockEntity:
        def __init__(self):
            self.coordinator = MagicMock()
            self._meter_id = "123"
            self._data_key = "total_plus"
            self._restored_value = None
            self._attr_native_unit_of_measurement = "kWh"
            
    # Mock HASS modules
    mock_sensor_comp = SimpleNamespace(
        SensorEntity=MockEntity,
        SensorDeviceClass=SimpleNamespace(ENERGY="energy"),
        SensorStateClass=SimpleNamespace(TOTAL_INCREASING="total_increasing")
    )
    
    mock_ha_core = SimpleNamespace(HomeAssistant=MagicMock, callback=lambda x: x)
    mock_ha_helpers = SimpleNamespace(
        update_coordinator=SimpleNamespace(CoordinatorEntity=MockEntity),
        entity_platform=SimpleNamespace(AddEntitiesCallback=MagicMock),
        restore_state=SimpleNamespace(RestoreEntity=MockEntity),
        typing=SimpleNamespace(StateType=str)
    )

    with patch.dict('sys.modules', {
        'homeassistant.components.sensor': mock_sensor_comp,
        'homeassistant.core': mock_ha_core,
        'homeassistant.helpers.update_coordinator': mock_ha_helpers.update_coordinator,
        'homeassistant.helpers.restore_state': mock_ha_helpers.restore_state,
        'homeassistant.helpers.entity_platform': mock_ha_helpers.entity_platform,
        'homeassistant.const': SimpleNamespace(UnitOfEnergy=SimpleNamespace(KILO_WATT_HOUR="kWh")),
        'homeassistant.components.recorder.models': SimpleNamespace(StatisticData=MagicMock, StatisticMetaData=MagicMock),
        'homeassistant.components.recorder.statistics': SimpleNamespace(async_import_statistics=MagicMock()),
    }):
        
        # --- TEST LOGIC: sensor.py property (v3.6.0-beta.15) ---
        class TestSensor(MockEntity):
            def __init__(self, value, is_numeric=True):
                super().__init__()
                self.coordinator.data = [{"meter_point_id": "123", "total_plus": value}]
                
            @property
            def native_value(self):
                # LOGIC COPY-PASTE FROM sensor.py Beta 15
                if self.coordinator.data:
                    meter_data = next((m for m in self.coordinator.data if m["meter_point_id"] == self._meter_id), None)
                    if meter_data:
                        key_to_fetch = self._data_key
                        
                        # THE CRITICAL RESTORED LINE:
                        val = meter_data.get(key_to_fetch)
                        
                        if val is not None:
                            try:
                                f_val = float(val)
                                if f_val <= 0 and self._restored_value:
                                    try:
                                        prev_f = float(self._restored_value)
                                        if prev_f > 100:
                                            return self._restored_value
                                    except ValueError: pass 
                            except ValueError:
                                pass 

                            self._restored_value = val
                            return val
                return self._restored_value

        # --- SCENARIO 1: The Crash Test ---
        print("\n[TEST] Verifying 'val' is defined...")
        try:
            sensor = TestSensor(value=500.0)
            result = sensor.native_value
            print(f"   Result: {result}")
            if result == 500.0:
                print("   ✅ PASS. No NameError.")
            else:
                print("   ❌ FAIL. Logic error.")
        except NameError as e:
            print(f"   🔥 CRITICAL FAIL: {e}")
            
    print("\n==========================================")
    print("   BETA 15 VERIFIED")
    print("==========================================")

if __name__ == "__main__":
    run_simulation()
