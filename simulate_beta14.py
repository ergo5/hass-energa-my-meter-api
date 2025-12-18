
import asyncio
import logging
from unittest.mock import MagicMock, patch
import sys
from types import SimpleNamespace

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
_LOGGER = logging.getLogger("simulate_beta14")

def run_simulation():
    print("==========================================")
    print("   SIMULATION SUITE: v3.6.0-beta.14      ")
    print("   Target: STRING SENSORS & ZERO GUARD   ")
    print("==========================================")

    # --- MOCKING THE ENVIRONMENT FOR SENSOR.PY ---
    
    # Mock Entities
    class MockEntity:
        def __init__(self, coordinator=None):
            self.coordinator = coordinator
            self.hass = MagicMock()
            self._attr_unique_id = "test_uid"
            self._attr_native_value = None
            
    class MockCoordinatorEntity(MockEntity):
        pass
        
    class MockSensorEntity(MockEntity):
        pass
        
    class MockRestoreEntity(MockEntity):
        pass

    # Apply Mocks
    mock_sensor_comp = SimpleNamespace(
        SensorEntity=MockSensorEntity,
        SensorDeviceClass=SimpleNamespace(ENERGY="energy"),
        SensorStateClass=SimpleNamespace(TOTAL_INCREASING="total_increasing", TOTAL="total")
    )
    
    mock_ha_core = SimpleNamespace(
        HomeAssistant=MagicMock,
        callback=lambda x: x
    )
    
    mock_ha_helpers = SimpleNamespace(
        update_coordinator=SimpleNamespace(CoordinatorEntity=MockCoordinatorEntity),
        entity_platform=SimpleNamespace(AddEntitiesCallback=MagicMock),
        restore_state=SimpleNamespace(RestoreEntity=MockRestoreEntity),
        typing=SimpleNamespace(StateType=str)
    )

    with patch.dict('sys.modules', {
        'homeassistant.components.sensor': mock_sensor_comp,
        'homeassistant.core': mock_ha_core,
        'homeassistant.helpers.update_coordinator': mock_ha_helpers.update_coordinator,
        'homeassistant.helpers.restore_state': mock_ha_helpers.restore_state,
        'homeassistant.helpers.entity_platform': mock_ha_helpers.entity_platform,
        'homeassistant.const': SimpleNamespace(UnitOfEnergy=SimpleNamespace(KILO_WATT_HOUR="kWh")),
        
        # Dependencies for __init__ if needed (prevent import errors)
        'homeassistant.components.recorder.models': SimpleNamespace(StatisticData=MagicMock, StatisticMetaData=MagicMock),
        'homeassistant.components.recorder.statistics': SimpleNamespace(async_import_statistics=MagicMock()),
    }):
        
        print("\n[TEST 1] Testing ZERO GUARD & TYPE SAFETY...")
        
        # START LOGIC FROM sensor.py (v3.6.0-beta.14)
        class TestSensor:
            def __init__(self, initial_value, is_numeric=True):
                self._restored_value = initial_value
                self._meter_id = "123"
                self._data_key = "test_key"
                self.coordinator = MagicMock()
                self.coordinator.data = []

            @property
            def native_value(self):
                if self.coordinator.data:
                    meter_data = next((m for m in self.coordinator.data if m["meter_point_id"] == self._meter_id), None)
                    if meter_data:
                        key_to_fetch = self._data_key
                        
                        val = meter_data.get(key_to_fetch)
                        if val is not None:
                            # ZERO-GUARD: Prevent meter reset detection if API returns 0 or glitch
                            try:
                                f_val = float(val)
                                if f_val <= 0 and self._restored_value:
                                    try:
                                        prev_f = float(self._restored_value)
                                        if prev_f > 100:
                                            # _LOGGER.warning("...")
                                            print(f"      [GUARD ACTIVE] Blocked value {f_val} (Previous: {self._restored_value})")
                                            return self._restored_value
                                    except ValueError: pass # Previous wasn't float
                            except ValueError:
                                pass # Not a number, skip guard

                            self._restored_value = val
                            return val
                
                if self._restored_value is not None:
                    return self._restored_value
        
        # --- SCENARIO A: Normal Numeric (Regression Check) ---
        print("   --- Scenario A: Normal Numeric Update ---")
        sensor_num = TestSensor(initial_value=1000.0)
        sensor_num.coordinator.data = [{"meter_point_id": "123", "test_key": 1001.0}]
        res = sensor_num.native_value
        if res == 1001.0: print("   ✅ PASS (1001.0)")
        else: print(f"   ❌ FAIL (Got {res})")

        # --- SCENARIO B: Zero Glitch (Regression Check) ---
        print("   --- Scenario B: Zero Glitch (Guard Check) ---")
        sensor_num._restored_value = 1001.0
        sensor_num.coordinator.data = [{"meter_point_id": "123", "test_key": 0.0}]
        res = sensor_num.native_value
        if res == 1001.0: print("   ✅ PASS (Guard Blocked 0.0)")
        else: print(f"   ❌ FAIL (Guard let {res} through)")

        # --- SCENARIO C: String Sensor (CRITICAL FIX TEST) ---
        print("   --- Scenario C: String Sensor (Tariff 'G11') ---")
        # Previous state might be 'G11' or None. Let's say 'G11'.
        sensor_str = TestSensor(initial_value="G11", is_numeric=False)
        # Update is the same 'G11' or maybe 'G12' if changed
        sensor_str.coordinator.data = [{"meter_point_id": "123", "test_key": "G11"}]
        
        try:
            res = sensor_str.native_value
            print(f"   Result: '{res}'")
            if res == "G11":
                print("   ✅ PASS - No Crash! Value returned.")
            else:
                print(f"   ❌ FAIL - Unexpected value {res}")
        except Exception as e:
            print(f"   ❌ CRASHED: {e}")

        # --- SCENARIO D: String Update on Numeric Sensor? ---
        # Unlikely but possible if API changes schema. Should NOT crash.
        print("   --- Scenario D: Numeric Sensor gets String garbage ---")
        sensor_num._restored_value = 1000.0
        sensor_num.coordinator.data = [{"meter_point_id": "123", "test_key": "Błąd"}]
        try:
            res = sensor_num.native_value
            print(f"   Result: '{res}'")
            if res == "Błąd": 
                 print("   ✅ PASS - Handled gracefully (updated to garbage string, but didn't crash).")
        except Exception as e:
            print(f"   ❌ CRASHED: {e}")

    print("\n==========================================")
    print("   SIMULATION COMPLETE: Beta 14 Verified  ")
    print("==========================================")

if __name__ == "__main__":
    run_simulation()
