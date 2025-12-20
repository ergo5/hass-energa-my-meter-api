
import sqlite3
import datetime
import os

DB_PATH = r"y:\home-assistant_v2.db"

def check_values():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()

    try:
        entities = [
            "sensor.energa_import_panel_energia",
            "sensor.energa_export_panel_energia"
        ]
        
        for entity in entities:
            # Get metadata_id from states_meta
            cursor.execute("SELECT metadata_id FROM states_meta WHERE entity_id = ?", (entity,))
            row = cursor.fetchone()
            
            if row:
                mid = row[0]
                # Get last state
                cursor.execute("SELECT last_updated_ts, state FROM states WHERE metadata_id = ? ORDER BY last_updated_ts DESC LIMIT 5", (mid,))
                rows = cursor.fetchall()
                
                print(f"\nEntity: {entity} (Metadata ID: {mid})")
                if rows:
                    for r in rows:
                        ts = datetime.datetime.fromtimestamp(r[0])
                        print(f" - {ts} | State: {r[1]}")
                else:
                    print(f" -> NO STATES recorded.")

                # Also check statistics_short_term
                cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = ?", (entity,))
                stat_meta = cursor.fetchone()
                if stat_meta:
                    sid = stat_meta[0]
                    cursor.execute("SELECT count(*) FROM statistics_short_term WHERE metadata_id = ?", (sid,))
                    count = cursor.fetchone()[0]
                    print(f" -> Statistics Rows: {count}")
                else:
                    print(" -> No Statistics Metadata yet.")

            else:
                print(f"\nEntity: {entity} -> Not found in states_meta")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_values()
