"""Analyze statistics data for December 20, 2025 to find the issue"""

import sqlite3
from datetime import datetime

DB_PATH = r"Y:\home-assistant_v2.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# December 20, 2025 timestamps
day_start = datetime(2025, 12, 20, 0, 0, 0).timestamp()
day_end = datetime(2025, 12, 21, 0, 0, 0).timestamp()

print("=" * 80)
print("ANALYZING DECEMBER 20, 2025 STATISTICS")
print("=" * 80)

# Get metadata for Panel Energia sensors
cursor.execute("""
    SELECT id, statistic_id, source 
    FROM statistics_meta 
    WHERE statistic_id LIKE '%panel_energia%'
    ORDER BY id
""")

metadata = cursor.fetchall()
print(f"\nFound {len(metadata)} Panel Energia sensors:")
for row in metadata:
    print(f"  ID {row[0]}: {row[1]} (source={row[2]})")

if not metadata:
    print("\n❌ No Panel Energia sensors found! Cannot analyze.")
    conn.close()
    exit(1)

# Analyze each sensor
for meta_id, stat_id, source in metadata:
    print(f"\n{'=' * 80}")
    print(f"Sensor: {stat_id} (metadata_id={meta_id})")
    print(f"{'=' * 80}")

    # Get statistics for Dec 20
    cursor.execute(
        """
        SELECT 
            datetime(start_ts, 'unixepoch', 'localtime') as time,
            start_ts,
            state,
            sum,
            created_ts
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
        print("  ❌ No statistics for Dec 20")
        continue

    print(f"\n  Found {len(stats)} hour records:")
    print(f"  {'Time':<20} {'State (kWh)':<15} {'Sum (kWh)':<15} {'Created':<20}")
    print(f"  {'-' * 70}")

    issues = []
    prev_sum = None

    for row in stats:
        time_str, ts, state, sum_val, created = row
        created_str = (
            datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")
            if created
            else "N/A"
        )

        print(f"  {time_str:<20} {state:<15.3f} {sum_val:<15.3f} {created_str:<20}")

        # Check for anomalies
        if state and abs(state) > 100:  # More than 100 kWh in one hour is suspicious
            issues.append(
                f"    ⚠️ {time_str}: Suspicious state={state:.3f} kWh (>100 kWh/hour!)"
            )

        if prev_sum is not None and sum_val is not None:
            delta = sum_val - prev_sum
            if abs(delta - state) > 0.01:  # Delta should equal state
                issues.append(
                    f"    ❌ {time_str}: Sum delta ({delta:.3f}) != state ({state:.3f})"
                )

        prev_sum = sum_val

    if issues:
        print("\n  🔍 ISSUES FOUND:")
        for issue in issues:
            print(issue)
    else:
        print("\n  ✅ No obvious issues")

    # Check for duplicates
    cursor.execute(
        """
        SELECT start_ts, COUNT(*) as count
        FROM statistics
        WHERE metadata_id = ?
          AND start_ts >= ?
          AND start_ts < ?
        GROUP BY start_ts
        HAVING COUNT(*) > 1
    """,
        (meta_id, day_start, day_end),
    )

    duplicates = cursor.fetchall()
    if duplicates:
        print("\n  ⚠️ DUPLICATES FOUND:")
        for ts, count in duplicates:
            dt = datetime.fromtimestamp(ts)
            print(f"    {dt}: {count} records")

conn.close()

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
