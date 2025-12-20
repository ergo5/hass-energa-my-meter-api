
import sqlite3
import datetime
import os

DB_PATH = r"y:\home-assistant_v2.db"

def verify_fresh():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()

    try:
        # Check for Metadata
        cursor.execute("SELECT id, statistic_id, source FROM statistics_meta WHERE statistic_id LIKE '%energa%'")
        rows = cursor.fetchall()
        
        if not rows:
            print("NO Energa sensors found in 'statistics_meta'. Integration might not be configured/logged in yet.")
        else:
            print(f"Found {len(rows)} Energa sensors in metadata:")
            for r in rows:
                print(f" - ID: {r[0]} | Name: {r[1]} | Source: {r[2]}")
                
                # Check for any data
                meta_id = r[0]
                cursor.execute("SELECT count(*) FROM statistics_short_term WHERE metadata_id = ?", (meta_id,))
                count = cursor.fetchone()[0]
                print(f"   -> Data rows: {count}")

        # Check States table just in case
        cursor.execute("SELECT entity_id FROM states_meta WHERE entity_id LIKE '%energa%'")
        state_rows = cursor.fetchall()
        if state_rows:
             print(f"\nFound {len(state_rows)} Energa entities in 'states_meta':")
             for sr in state_rows:
                 print(f" - {sr[0]}")
        else:
             print("\nNo Energa entities in 'states_meta'.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_fresh()
