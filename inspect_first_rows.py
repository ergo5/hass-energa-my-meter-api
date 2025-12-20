
import sqlite3
import datetime
import os

DB_PATH = r"y:\home-assistant_v2.db"

def inspect_first_rows():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()

    try:
        sensor_name = "sensor.energa_import_panel_energia"
        cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = ?", (sensor_name,))
        meta_row = cursor.fetchone()
        
        if meta_row:
            meta_id = meta_row[0]
            # Fetch FIRST 5 rows ever
            cursor.execute("SELECT start_ts, state, sum FROM statistics_short_term WHERE metadata_id = ? ORDER BY start_ts ASC LIMIT 5", (meta_id,))
            rows = cursor.fetchall()
            
            print(f"\nScanning FIRST entries for {sensor_name} (id={meta_id}):")
            for r in rows:
                ts = datetime.datetime.fromtimestamp(r[0])
                state = r[1]
                s_sum = r[2]
                print(f"Time: {ts} | State: {state} | Sum: {s_sum}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_first_rows()
