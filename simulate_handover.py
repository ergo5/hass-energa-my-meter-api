
import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

@dataclass
class StatData:
    start: datetime
    state: float
    sum: float

# --- LOGIC UNDER TEST (Copied from __init__.py Beta 14) ---
# We isolate the mathematical core: "process_and_import" logic
# adjusted to run standalone.

def simulate_import_logic(data_list_input, anchor_sum):
    # data_list expects dicts with "dt" and "val"
    # Logic from lines 189-204 of __init__.py
    
    # 1. Sort Newest First
    data_list = sorted(data_list_input, key=lambda x: x["dt"], reverse=True)
    
    running_sum = anchor_sum
    processed_stats = []
    
    print(f"   [LOGIC] Starting Backward Loop. Anchor (Now): {anchor_sum}")
    
    for item in data_list:
        dt = item["dt"]
        val = item["val"]
        
        # In current code, we append State = Running Sum
        # Then subtract val.
        # This means the timestamp 'dt' (e.g. 14:00) gets the value at the END of that hour?
        # Let's verify 'dt'.
        # In __init__.py: dt_hour = day_start + timedelta(hours=h+1)
        # So 'dt' is the END of the hour (e.g. 01:00 for 00:00-01:00 interval).
        
        # So at 14:00 (End of hour), the Total State IS 'running_sum' (which equals Anchor if it's the latest).
        
        processed_stats.append(StatData(start=dt, state=running_sum, sum=running_sum))
        
        # Then we step back to start of hour
        running_sum -= val
        
    # Sort back to chronological for display/storage
    processed_stats.sort(key=lambda x: x.start)
    return processed_stats

# --- SIMULATION RUNNER ---
def run_handover_test():
    print("==========================================")
    print("   SIMULATION SUITE: HANDOVER BOUNDARY   ")
    print("   Target: History Import -> Live Mode   ")
    print("==========================================")
    
    # Scenario:
    # Current Time: 12:00
    # Meter Total: 5000.0 kWh (Anchor)
    # We have data for today: 00:00 -> 12:00.
    # Hourly usage: 1.0 kWh per hour.
    
    ANCHOR_TOTAL = 5000.0
    HOURLY_USAGE = 1.0
    HOURS_TODAY = 12
    
    # 1. Generate Mock API History Data
    # Timestamps are "End of Hour"
    mock_history_data = []
    base_time = datetime(2025, 12, 18, 0, 0, 0) # Start of day
    
    for h in range(HOURS_TODAY):
        # h=0 -> 01:00, h=11 -> 12:00
        dt_hour = base_time + timedelta(hours=h+1)
        mock_history_data.append({
            "dt": dt_hour,
            "val": HOURLY_USAGE,
            "daily_state": 0 # Irrelevant for Total check
        })
        
    print(f"   [SCENARIO] 12 Hours of Data. Total Usage: {HOURS_TODAY * HOURLY_USAGE}")
    print(f"   [SCENARIO] Current API Total (Anchor): {ANCHOR_TOTAL}")
    
    # 2. Run Import Logic
    stats = simulate_import_logic(mock_history_data, ANCHOR_TOTAL)
    
    # 3. Analyze The "Handover" Point (The latest stat)
    latest_stat = stats[-1]
    
    print("\n   [RESULTS] Imported Stats (Last 3):")
    for s in stats[-3:]:
        print(f"      Time: {s.start.time()} | State: {s.state}")
        
    print(f"\n   [HANDOVER CHECK]")
    print(f"   1. Live Sensor Value (Now): {ANCHOR_TOTAL}")
    print(f"   2. History Last Point ({latest_stat.start.time()}): {latest_stat.state}")
    
    diff = abs(ANCHOR_TOTAL - latest_stat.state)
    print(f"   -> Difference: {diff}")
    
    if diff < 0.001:
        print("   ✅ PERFECT MATCH. No Spike.")
    else:
        print("   ❌ SPIKE DETECTED! Logic mismatch.")

    # 4. Analyze "Start of Day" Consistency
    # If we walked back correctly:
    # Anchor (5000) - 12 hours * 1 = 4988.
    # The first point (01:00) should be 4988 + 1 = 4989.
    # Wait.
    # 12:00 -> 5000
    # 11:00 -> 4999
    # ...
    # 01:00 -> 4989
    # Start of Day (00:00) state would be 4988.
    
    first_stat = stats[0]
    expected_first = ANCHOR_TOTAL - (HOURS_TODAY * HOURLY_USAGE) + HOURLY_USAGE
    
    print(f"\n   [CONSISTENCY CHECK]")
    print(f"   First Point ({first_stat.start.time()}): {first_stat.state}")
    print(f"   Expected: {expected_first}")
    
    if abs(first_stat.state - expected_first) < 0.001:
         print("   ✅ MATH CONSISTENT.")
    else:
         print("   ❌ BACKWARD CALCULATION ERROR.")

if __name__ == "__main__":
    run_handover_test()
