
import sqlite3
import datetime
import os

DB_PATH = r"y:\home-assistant_v2.db"

def inspect_long_term():
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
            print(f"\nChecking LONG TERM stats for {sensor_name} (id={meta_id}):")
            
            # Fetch first 10 rows
            cursor.execute("SELECT start_ts, state, sum FROM statistics WHERE metadata_id = ? ORDER BY start_ts ASC LIMIT 10", (meta_id,))
            rows = cursor.fetchall()
            
            if not rows:
                print(" -> No Long Term stats found.")
            else:
                prev_sum = None
                for r in rows:
                    ts = datetime.datetime.fromtimestamp(r[0])
                    state = r[1]
                    s_sum = r[2]
                    
                    diff = 0
                    if prev_sum is not None:
                        diff = s_sum - prev_sum
                        
                    print(f"Time: {ts} | State: {state} | Sum: {s_sum} | Diff: {diff}")
                    
                    if abs(diff) > 1000:
                        print("  ^^^ SPIKE DETECTED ^^^")
                    
                    prev_sum = s_sum
                    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_long_term()
