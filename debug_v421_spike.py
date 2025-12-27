"""Debug v4.2.1 - check why spike still occurs"""

import sqlite3
from datetime import datetime

import requests

HA_URL = "http://192.168.70.199:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3MTQ5ZWJiZTg0OWM0ZmE3OTBlOGFmNGZiOTlmNDg5NiIsImlhdCI6MTc2NjY4MzcyMCwiZXhwIjoyMDgyMDQzNzIwfQ.QL2li2QXirbu7UaSBuZadZVK34NHOqAKeZ-BJAPGGRc"
headers = {"Authorization": f"Bearer {TOKEN}"}

print("=" * 80)
print("DEBUG: v4.2.1 Spike Investigation")
print("=" * 80)

# Check database for Dec 1 statistics
conn = sqlite3.connect(r"Y:\home-assistant_v2.db")
cursor = conn.cursor()

dec1_start = datetime(2025, 12, 1, 0, 0, 0).timestamp()
dec1_end = datetime(2025, 12, 2, 0, 0, 0).timestamp()

print("\n[1/3] Checking Dec 1 statistics in database...")
cursor.execute(
    """
    SELECT 
        datetime(start_ts, 'unixepoch', 'localtime') as time,
        state,
        sum,
        datetime(created_ts, 'unixepoch', 'localtime') as created
    FROM statistics
    WHERE metadata_id = 13
      AND start_ts >= ?
      AND start_ts < ?
    ORDER BY start_ts
    LIMIT 5
""",
    (dec1_start, dec1_end),
)

rows = cursor.fetchall()
print("\nFirst 5 entries for Dec 1:")
print(f"{'Time':<20} {'State':<12} {'Sum':<15} {'Created'}")
print("-" * 70)

for row in rows:
    time_str, state, sum_val, created = row
    print(f"{time_str:<20} {state:<12.3f} {sum_val:<15.3f} {created}")

if rows:
    first_sum = rows[0][2]
    if first_sum < 100:
        print(f"\n❌ PROBLEM: First sum={first_sum:.3f} (should be ~24,500)")
        print("   Intelligent initialization DID NOT WORK")
    else:
        print(f"\n✅ First sum={first_sum:.3f} looks correct")

conn.close()

# Check HA logs for initialization messages
print("\n[2/3] Checking HA logs for initialization messages...")
try:
    response = requests.get(f"{HA_URL}/api/error_log", headers=headers, timeout=10)
    log = response.text

    # Search for our debug messages
    log_lines = log.split("\n")
    found_init_messages = []

    for line in log_lines[-500:]:  # Last 500 lines
        if "Statistics:" in line and ("base=" in line or "Continuing from" in line):
            found_init_messages.append(line)

    if found_init_messages:
        print("Found initialization messages:")
        for msg in found_init_messages[-5:]:
            print(f"  {msg[:150]}")
    else:
        print("❌ NO initialization debug messages found!")
        print("   This means the intelligent initialization code didn't execute")

except Exception as e:
    print(f"Error reading logs: {e}")

# Check if hass reference was set
print("\n[3/3] Diagnosis...")
if not found_init_messages:
    print("\n🔍 ROOT CAUSE CANDIDATES:")
    print("1. hasattr(self, '_hass') returned False")
    print("2. Exception in try/except block (silent failure)")
    print("3. Code path didn't execute at all")
    print("\nNeed to add explicit logging to confirm which scenario.")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("Add explicit error logging to api.py to trace execution path")
print("Check which branch of if/else was taken")
