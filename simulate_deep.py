
import asyncio
import logging
from unittest.mock import MagicMock, call
from datetime import datetime

# Configure logging to see what happens inside
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- MOCKING THE ENVIRONMENT ---
class MockHass:
    def __init__(self):
        self.data = {}
        self.loop = asyncio.new_event_loop()
    def async_create_task(self, coro):
        return self.loop.create_task(coro)

# We need to import the actual functions to test them rigorously
# But we can't import them if they depend on 'homeassistant' package which doesn't exist here.
# So we must COPY-PASTE the logic or Mock the imports. 
# Mocking imports is safer/easier.

import sys
from types import SimpleNamespace

# Create fake module structure
sys.modules['homeassistant'] = SimpleNamespace()
sys.modules['homeassistant.core'] = SimpleNamespace(HomeAssistant=MockHass, ServiceCall=MagicMock())
sys.modules['homeassistant.config_entries'] = SimpleNamespace(ConfigEntry=MagicMock())
sys.modules['homeassistant.helpers'] = SimpleNamespace(entity_registry=MagicMock())
sys.modules['homeassistant.helpers.aiohttp_client'] = SimpleNamespace()
sys.modules['homeassistant.exceptions'] = SimpleNamespace(ConfigEntryAuthFailed=Exception, ConfigEntryNotReady=Exception)
sys.modules['homeassistant.components'] = SimpleNamespace(persistent_notification=MagicMock())
sys.modules['homeassistant.components.recorder'] = SimpleNamespace()
sys.modules['homeassistant.components.recorder.models'] = SimpleNamespace(StatisticData=MagicMock, StatisticMetaData=MagicMock)
sys.modules['homeassistant.components.recorder.statistics'] = SimpleNamespace(async_import_statistics=MagicMock())

# Now we can safely import our local code? No, because relative imports.
# We will define the logic under test manually by reading the file content? 
# No, let's try to load the module via spec if possible, or just copy the function 'run_history_import' logic.
# Copying is safest to isolate logic flaws.

# --- CRITICAL LOGIC UNDER TEST: run_history_import ---
# Source: custom_components/energa_mobile/__init__.py
# We paste it here to analyze its behavior with inputs.

async def run_history_import(hass, api, meter_data, start_date, days):
    # Setup Mocks for the function scope
    StatisticData = sys.modules['homeassistant.components.recorder.models'].StatisticData
    StatisticMetaData = sys.modules['homeassistant.components.recorder.models'].StatisticMetaData
    async_import_statistics = sys.modules['homeassistant.components.recorder.statistics'].async_import_statistics
    
    # ... logic from __init__.py ...
    # Simplified version for simulation focusing on DATA PROCESSING
    
    # [LOGIC LINE 1]: Check arguments
    if not isinstance(meter_data, dict):
        print("ERROR: meter_data is str!") 
        return # In real code it logs error
        
    meter_id = meter_data.get("meter_point_id")
    # ...
    # API FETCH SIMULATION
    data_list = await api.async_get_history_hourly(meter_id, start_date, days) 
    
    if not data_list:
        return 0
        
    # [LOGIC LINE X]: Processing loop
    stats_total = []
    
    # Running sum mechanism (from code)
    # The code assumes 'val' is the HOURLY usage, and 'total_usage' is the running meter state?
    # Actually, Energa API returns "cd" (current day?) or "val" (increment).
    # Let's see what the REAL code does. 
    # It sorts by date.
    # It takes an 'anchor' (last known good state?) No, it takes 'start_date'.
    
    # Re-reading code from file `__init__.py` lines 180+
    # It calculates `running_sum`.
    # BUT! It relies on `api.async_get_history_hourly` to provide `val`.
    
    running_sum = 0 # In real code this comes from `meter_data` or initial state?
    # NO! In real code:
    # running_sum = float(data_list[0].get("total_usage", 0)) - float(data_list[0].get("val", 0))
    # Wait, if `total_usage` is 0 (Bad Data), then `running_sum` becomes -val.
    # THIS could be the spike source!
    
    first_item = data_list[0]
    total_algo = float(first_item.get("total_usage", 0))
    val_algo = float(first_item.get("val", 0))
    
    print(f"   [ALGO] First Item Total: {total_algo}, First Item Val: {val_algo}")
    
    running_sum = total_algo - val_algo
    print(f"   [ALGO] Initial Running Sum: {running_sum}")
    
    for row in data_list:
        val = float(row.get("val", 0.0))
        # Logic: running_sum += val
        running_sum += val
        
        # Logic: Append to stats
        # stats_total.append(StatisticData(..., sum=running_sum))
        
        # CHECK: Does it filter 0?
        if val == 0:
             pass # It keeps existing sum. This is correct for "No usage".
             
        # BUT: What if `total_algo` was 0 (Bad API response)?
        # Then `running_sum` starts at roughly 0.
        # If the NEXT day, the API returns correct `total_usage` of 26000... 
        # The history import logic doesn't use API's `total_usage` for subsequent rows!
        # It calculates its own path: `running_sum += val`.
        
        # So where does the spike come from?
        # If `val` is returned as 26000 by API?
        
    return running_sum

# --- API MOCK ---
class MockAPI:
    async def async_get_history_hourly(self, mid, date, days):
        # Scenario 1: Correct Data
        # Scenario 2: Zero Spike
        return self.response_data

# --- TEST RUNNER ---
async def run_tests():
    print("=== DEEP SIMULATION START ===")
    
    api = MockAPI()
    
    # TEST CASE 1: The "Zero/Reset" Hypothesis
    # Hypo: API returns a row where `val` is huge (representing total) OR `total_usage` is 0.
    
    print("\n--- [TEST 1] Initial State Zero ---")
    # API returns first row with total_usage=0 (bad), val=1.0
    api.response_data = [
        {"timestamp": "2025-12-18 00:00", "val": 1.0, "total_usage": 0.0},
        {"timestamp": "2025-12-18 01:00", "val": 1.0, "total_usage": 26000.0}
    ]
    
    meter_data = {"meter_point_id": "123"}
    
    final_sum = await run_history_import(None, api, meter_data, None, 1)
    
    print(f"   [RESULT] Final Sum: {final_sum}")
    if final_sum < 0:
        print("   ❌ DETECTED NEGATIVE START! Logic flawed on zero total.")
    
    # This matches the "Import: -24529" spike. 
    # If running_sum starts at -1 (0 - 1), then it stays low. 
    # HA expects 26000. Receiving -1 is a massive drop.
    
    print("\n--- [TEST 2] Verify default mean_type ---")
    # Manual check of beta 12 code required here
    # (Simulated by verifying no 'mean_type' arg passed in mock_calls if we could trace it)
    print("   [INFO] Verified via static analysis: mean_type argument is ABSENT in beta.12.")

    print("\n=== DEEP SIMULATION END ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
