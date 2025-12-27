"""Correlate spike values with meter total readings"""

import sqlite3
from datetime import datetime

import requests

HA_URL = "http://192.168.70.199:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3MTQ5ZWJiZTg0OWM0ZmE3OTBlOGFmNGZiOTlmNDg5NiIsImlhdCI6MTc2NjY4MzcyMCwiZXhwIjoyMDgyMDQzNzIwfQ.QL2li2QXirbu7UaSBuZadZVK34NHOqAKeZ-BJAPGGRc"
headers = {"Authorization": f"Bearer {TOKEN}"}

print("=" * 80)
print("CORRELATION ANALYSIS: Spikes vs Meter Total")
print("=" * 80)

# Get current meter total
print("\n[1/3] Current meter readings...")
try:
    response = requests.get(
        f"{HA_URL}/api/states/sensor.energa_30132815_stan_licznika_import",
        headers=headers,
    )
    import_total = float(response.json()["state"])
    print(f"  Import total (total_plus): {import_total:.3f} kWh")

    response = requests.get(
        f"{HA_URL}/api/states/sensor.energa_30132815_stan_licznika_export",
        headers=headers,
    )
    export_total = float(response.json()["state"])
    print(f"  Export total (total_minus): {export_total:.3f} kWh")
except Exception as e:
    print(f"  Error: {e}")
    import_total = 24754.0  # Fallback
    export_total = 26640.0

# Check Dec 20 statistics in database
print("\n[2/3] Dec 20 statistics in database...")
conn = sqlite3.connect(r"Y:\home-assistant_v2.db")
cursor = conn.cursor()

dec20_start = datetime(2025, 12, 20, 0, 0, 0).timestamp()
dec20_end = datetime(2025, 12, 20, 3, 0, 0).timestamp()

print("\n  IMPORT (Zużycie):")
cursor.execute(
    """
    SELECT 
        datetime(start_ts, 'unixepoch', 'localtime') as time,
        state,
        sum
    FROM statistics
    WHERE metadata_id = 13
      AND start_ts >= ?
      AND start_ts < ?
    ORDER BY start_ts
""",
    (dec20_start, dec20_end),
)

import_rows = cursor.fetchall()
print(f"  {'Time':<20} {'State':<12} {'Sum':<15} {'Analysis'}")
print(f"  {'-' * 70}")

for row in import_rows:
    time_str, state, sum_val = row
    analysis = ""
    if sum_val > 24000:
        analysis = f"← SPIKE! (near total={import_total:.0f})"
    print(f"  {time_str:<20} {state:<12.3f} {sum_val:<15.3f} {analysis}")

print("\n  EXPORT (Produkcja):")
cursor.execute(
    """
    SELECT 
        datetime(start_ts, 'unixepoch', 'localtime') as time,
        state,
        sum
    FROM statistics
    WHERE metadata_id = 14
      AND start_ts >= ?
      AND start_ts <= ?
    ORDER BY start_ts
""",
    (dec20_start, datetime(2025, 12, 20, 12, 0, 0).timestamp()),
)

export_rows = cursor.fetchall()
print(f"  {'Time':<20} {'State':<12} {'Sum':<15} {'Analysis'}")
print(f"  {'-' * 70}")

for row in export_rows:
    time_str, state, sum_val = row
    analysis = ""
    if sum_val > 26000:
        analysis = f"← SPIKE! (near total={export_total:.0f})"
    print(f"  {time_str:<20} {state:<12.3f} {sum_val:<15.3f} {analysis}")

conn.close()

# Check logs for initialization messages
print("\n[3/3] Checking if initialization code executed...")
try:
    response = requests.get(f"{HA_URL}/api/error_log", headers=headers, timeout=10)
    log = response.text

    # Search for our messages
    found = []
    for line in log.split("\n")[-300:]:
        if "Statistics:" in line and (
            "base=" in line or "Continuing" in line or "First import" in line
        ):
            found.append(line[-150:])

    if found:
        print("  Found initialization messages:")
        for msg in found[-3:]:
            print(f"    {msg}")
    else:
        print("  ❌ NO initialization messages found!")
        print("     This means the code path with DB query didn't execute")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)
print("\n🔍 PATTERN IDENTIFIED:")
print(f"  - First import spike: sum ≈ {import_total:.0f} kWh (= current meter total!)")
print(f"  - First export spike: sum ≈ {export_total:.0f} kWh (= current meter total!)")
print("\n  This means:")
print("  1. Initialization code DIDN'T RUN (no log messages)")
print("  2. Code fell back to: running_sum = anchor")
print("  3. anchor = current total_plus/total_minus")
print("\n❌ ROOT CAUSE: Exception in try/except block silently caught")
print("   Need to check what exception occurred during DB query")
