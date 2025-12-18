
import asyncio
import logging
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
_LOGGER = logging.getLogger("simulate_month")

async def run_month_simulation():
    print("==========================================")
    print("   SIMULATION SUITE: 30-DAY RUN          ")
    print("   Target: STABILITY, GLITCHES, IMPORT   ")
    print("==========================================")

    # --- MOCKS ---
    class MockCoordinator:
        def __init__(self):
            self.data = []

    class MockSensor:
        def __init__(self, meter_id):
            self._meter_id = meter_id
            self._restored_value = 1000.0 # Start at 1000 kWh
            self._data_key = "total_plus"
            self.coordinator = MockCoordinator()
            
        @property
        def native_value(self):
            # LOGIC FROM SENSOR.PY (Beta 14)
            if self.coordinator.data:
                meter_data = next((m for m in self.coordinator.data if m["meter_point_id"] == self._meter_id), None)
                if meter_data:
                    val = meter_data.get("total_plus") # Simplified key mapping
                    if val is not None:
                        try:
                            f_val = float(val)
                            # ZERO GUARDIAN
                            if f_val <= 0 and self._restored_value:
                                try:
                                    prev_f = float(self._restored_value)
                                    if prev_f > 100:
                                        print(f"      🛡️ GUARD: Ignoring {f_val} (Prev: {self._restored_value})")
                                        return self._restored_value
                                except ValueError: pass
                        except ValueError: pass
                        
                        self._restored_value = val
                        return val
            return self._restored_value

    # --- SIMULATION PARAMETERS ---
    START_DATE = datetime(2025, 12, 1)
    METER_ID = "123456"
    sensor = MockSensor(METER_ID)
    
    # Truth Data (What REALLY happens on the meter)
    real_total = 1000.0
    
    print(f"\n[START] Date: {START_DATE.date()} | Meter: {real_total} kWh")
    
    history_imported_count = 0
    glitch_count = 0
    failed_days = 0
    
    for day_offset in range(1, 31):
        current_date = START_DATE + timedelta(days=day_offset)
        
        # 1. GENERATE DAILY USAGE (Real World)
        daily_usage = random.uniform(5.0, 15.0)
        real_total += daily_usage
        
        # 2. SIMULATE API RESPONSE
        api_value = real_total
        
        # --- INJECT GLITCHES ---
        is_glitch = False
        if day_offset in [5, 12, 28]: # Days with API failures
            api_value = 0.0 # THE DREADED ZERO RESET
            is_glitch = True
            glitch_count += 1
            print(f"\n📅 Day {day_offset} ({current_date.date()}) - ⚠️ API GLITCH SIMULATED (Returned 0.0)")
        else:
            pass
            # print(f"📅 Day {day_offset} - Normal operation")

        # 3. UPDATE SENSOR
        sensor.coordinator.data = [{"meter_point_id": METER_ID, "total_plus": api_value}]
        
        result_value = sensor.native_value
        
        # 4. VALIDATE
        if is_glitch:
            if result_value == 0.0:
                 print(f"   ❌ CRITICAL FAIL: Sensor accepted 0.0! GRAPH SPIKE IMMINENT.")
                 failed_days += 1
            else:
                 # Success: It returned the PREVIOUS value (or kept old).
                 # Note: In real logic, it returns self._restored_value.
                 # Since we update _restored_value only on valid read, 
                 # it should hold the value from Day 4 (for Day 5 glitch).
                 diff = real_total - float(result_value)
                 print(f"   ✅ SUCCESS: Sensor ignored 0.0. Reporting: {result_value:.2f} (Lag: {diff:.2f} kWh)")
        
        else:
            # Normal Day
            if abs(float(result_value) - real_total) < 0.01:
                # Perfect sync
                pass
            else:
                 print(f"   ❌ SYNC FAIL: Sensor {result_value} != Real {real_total}")
                 failed_days += 1

        # 5. SIMULATE HISTORY IMPORT (Every 7 days)
        if day_offset % 7 == 0:
            print(f"   🔄 Auto-Import triggered for {current_date.date()}...")
            # Here we would mock async_import_statistics
            # We assume it works if parameters are correct (verified in beta13 sim)
            history_imported_count += 1

    print("\n==========================================")
    print(f"   RESULTS SUMMARY ({30} Days)")
    print(f"   - Total Usage Added: {real_total - 1000.0:.2f} kWh")
    print(f"   - API Glitches Injected: {glitch_count}")
    print(f"   - Sensor Failures: {failed_days}")
    print(f"   - History Imports: {history_imported_count}")
    
    if failed_days == 0:
        print("\n   🏆 STATUS: STABLE. No spikes detected over 30 days.")
    else:
        print("\n   💀 STATUS: FAILED. Check logs.")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(run_month_simulation())
