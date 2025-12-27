"""Quick check of Energa statistics in database"""

import sqlite3

conn = sqlite3.connect(r"Y:\home-assistant_v2.db")
cursor = conn.cursor()

print("All Energa statistics metadata:")
cursor.execute(
    "SELECT id, statistic_id, source FROM statistics_meta WHERE statistic_id LIKE '%energa%' ORDER BY id"
)
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} (source={row[2]})")

conn.close()
