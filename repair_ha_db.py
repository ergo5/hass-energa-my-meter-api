
import sqlite3
import datetime
import os

DB_PATH = r"y:\home-assistant_v2.db"

def repair():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database: {DB_PATH}")
    # Connect in Read-Write mode
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True)
    cursor = conn.cursor()

    try:
        # 1. Identify Sensors
        sensors = [
            "sensor.energa_import_panel_energia",
            "sensor.energa_export_panel_energia"
        ]
        
        tables = ["statistics_short_term", "statistics"]
        total_fixed = 0

        for sensor_name in sensors:
            cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = ?", (sensor_name,))
            meta_row = cursor.fetchone()
            
            if not meta_row:
                print(f"Metadata not found for {sensor_name}")
                continue

            meta_id = meta_row[0]
            print(f"\nRepairing {sensor_name} (id={meta_id})...")

            for table in tables:
                # Criteria: State > 1000 (valid high reading) BUT Sum < 100 (corrupt/reset sum)
                query_count = f"SELECT count(*) FROM {table} WHERE metadata_id = ? AND state > 1000 AND sum < 100"
                cursor.execute(query_count, (meta_id,))
                count = cursor.fetchone()[0]
                
                if count > 0:
                    print(f" -> Found {count} corrupt rows in {table}. Fixing...")
                    query_update = f"UPDATE {table} SET sum = state WHERE metadata_id = ? AND state > 1000 AND sum < 100"
                    cursor.execute(query_update, (meta_id,))
                    fixed = cursor.rowcount
                    print(f"    Fixed {fixed} rows.")
                    total_fixed += fixed
                else:
                    print(f" -> {table}: Clean.")
            
        if total_fixed > 0:
            conn.commit()
            print(f"\nSUCCESS: Total {total_fixed} rows repaired. Database changes committed.")
        else:
            print("\nDatabase is clean. No changes made.")

    except Exception as e:
        print(f"Error during repair: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    repair()
