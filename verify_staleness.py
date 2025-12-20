
import sqlite3
import datetime
import os

DB_PATH = r"y:\home-assistant_v2.db"

def check_staleness():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()

    try:
        sensors = [
            "sensor.energa_import_panel_energia",
            "sensor.energa_export_panel_energia"
        ]
        
        for sensor_name in sensors:
            print(f"\nChecking: {sensor_name}")
            
            # 1. Check STATS (Short Term)
            cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = ?", (sensor_name,))
            meta_row = cursor.fetchone()
            
            if meta_row:
                meta_id = meta_row[0]
                cursor.execute("SELECT start_ts, state, sum FROM statistics_short_term WHERE metadata_id = ? ORDER BY start_ts DESC LIMIT 1", (meta_id,))
                last_stat = cursor.fetchone()
                
                if last_stat:
                    ts = datetime.datetime.fromtimestamp(last_stat[0])
                    now = datetime.datetime.now()
                    diff = now - ts
                    print(f"  [Statistics] Last entry: {ts} (Values: State={last_stat[1]}, Sum={last_stat[2]})")
                    print(f"  -> Age: {diff}")
                    if diff > datetime.timedelta(hours=2):
                        print("  -> WARNING: Statistics seem STALE (> 2h old)!")
                else:
                    print("  [Statistics] No entries found.")
            else:
                print("  [Statistics] Metadata not found.")

            # 2. Check STATES (Live Entity State)
            # This is trickier as metadata_id is for stats. We need to find the entity_id in 'states_meta' or similar in recent HA
            # HA 2023+ uses 'states_meta' to map entity_id to metadata_id for the 'states' table.
            
            cursor.execute("SELECT metadata_id FROM states_meta WHERE entity_id = ?", (sensor_name,))
            state_meta = cursor.fetchone()
            
            if state_meta:
                sm_id = state_meta[0]
                # 'states' table stores 'last_updated_ts'
                cursor.execute("SELECT last_updated_ts, state FROM states WHERE metadata_id = ? ORDER BY last_updated_ts DESC LIMIT 1", (sm_id,))
                last_state = cursor.fetchone()
                
                if last_state:
                    # timestamp might be float
                    ts = datetime.datetime.fromtimestamp(last_state[0])
                    now = datetime.datetime.now()
                    diff = now - ts
                    print(f"  [Live State] Last update: {ts} (State={last_state[1]})")
                    print(f"  -> Age: {diff}")
                    if diff > datetime.timedelta(minutes=65):
                         print("  -> WARNING: Live state seems STALE (API not fetching?)!")
                else:
                     print("  [Live State] No state history found.")
            else:
                # Fallback for older DB schemas or if mapping missing
                cursor.execute("SELECT last_updated, state FROM states WHERE entity_id = ? ORDER BY last_updated DESC LIMIT 1", (sensor_name,))
                last_state_legacy = cursor.fetchone()
                if last_state_legacy:
                     print(f"  [Live State Legacy] Found: {last_state_legacy}")
                else:
                     print("  [Live State] Metadata not found in states_meta.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_staleness()
