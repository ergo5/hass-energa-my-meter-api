"""Analyze Dec 20 data for metadata_id 13 and 14 (Panel Energia sensors)"""

import sqlite3
from datetime import datetime

DB_PATH = r"Y:\home-assistant_v2.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# December 20, 2025 timestamps
day_start = datetime(2025, 12, 20, 0, 0, 0).timestamp()
day_end = datetime(2025, 12, 21, 0, 0, 0).timestamp()

print("=" * 80)
print("DECEMBER 20, 2025 - PANEL ENERGIA STATISTICS")
print("=" * 80)

for meta_id, sensor_name in [(13, "Zużycie"), (14, "Produkcja")]:
    print(f"\n{sensor_name} (metadata_id={meta_id}):")
    print("-" * 80)

    cursor.execute(
        """
        SELECT 
            datetime(start_ts, 'unixepoch', 'localtime') as time,
            state,
            sum
        FROM statistics
        WHERE metadata_id = ?
          AND start_ts >= ?
          AND start_ts < ?
        ORDER BY start_ts
    """,
        (meta_id, day_start, day_end),
    )

    stats = cursor.fetchall()

    if not stats:
        print("  ❌ No data for Dec 20")
        continue

    print(f"\n  {'Hour':<20} {'State (kWh)':<15} {'Sum (kWh)':<15}")
    print(f"  {'-' * 50}")

    total_state = 0
    issues = []

    for row in stats:
        time_str, state, sum_val = row
        total_state += state if state else 0

        print(f"  {time_str:<20} {state:<15.3f} {sum_val:<15.3f}")

        # Flag suspicious values
        if state and abs(state) > 50:  # >50 kWh/hour is abnormal for home
            issues.append(f"    🚨 {time_str}: ABNORMAL state={state:.3f} kWh")

    print(f"\n  Total state sum: {total_state:.3f} kWh")

    if issues:
        print("\n  ⚠️ ISSUES:")
        for issue in issues:
            print(issue)

# Check what the hourly API actually returned for Dec 20
print(f"\n{'=' * 80}")
print("Checking API data that was imported...")
print("=" * 80)

# Check recent imports in homeassistant.log would show what was imported
# For now, let's check if there's pattern in the bad data

cursor.execute(
    """
    SELECT 
        metadata_id,
        datetime(start_ts, 'unixepoch', 'localtime') as time,
        state,
        sum,
        datetime(created_ts, 'unixepoch', 'localtime') as created
    FROM statistics
    WHERE metadata_id IN (13, 14)
      AND start_ts >= ?
      AND start_ts < ?
      AND ABS(state) > 100
    ORDER BY start_ts
""",
    (day_start, day_end),
)

bad_stats = cursor.fetchall()

if bad_stats:
    print(f"\nFound {len(bad_stats)} records with |state| > 100 kWh:")
    for row in bad_stats:
        meta_id, time_str, state, sum_val, created = row
        sensor = "Zużycie" if meta_id == 13 else "Produkcja"
        print(
            f"  {sensor} @ {time_str}: state={state:.1f}, sum={sum_val:.1f}, created={created}"
        )
else:
    print("\n✅ No extremely abnormal values found")

conn.close()

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
