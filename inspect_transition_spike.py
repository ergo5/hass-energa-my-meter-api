import sqlite3
import datetime
import os

DB_PATH = r"y:\home-assistant_v2.db"

def inspect_transition_spike():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()

    try:
        # Find the import sensor
        cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = 'sensor.energa_import_panel_energia'")
        row = cursor.fetchone()
        if not row:
            print("ERROR: sensor.energa_import_panel_energia not found!")
            return
        
        meta_id = row[0]
        print(f"Found sensor metadata ID: {meta_id}\n")
        
        # Get the last 20 rows from statistics_short_term to see the transition
        cursor.execute("""
            SELECT datetime(start_ts, 'unixepoch', 'localtime') as time, 
                   state, sum
            FROM statistics_short_term 
            WHERE metadata_id = ? 
            ORDER BY start_ts DESC 
            LIMIT 20
        """, (meta_id,))
        
        rows = cursor.fetchall()
        
        print("Last 20 Statistics Entries (Newest First):")
        print("=" * 70)
        
        prev_sum = None
        for r in rows:
            time_str = r[0]
            state = r[1]
            sum_val = r[2]
            
            diff = ""
            if prev_sum is not None:
                delta = sum_val - prev_sum
                diff = f" (Δ: {delta:+.2f})"
            
            print(f"{time_str} | State: {state:>10.3f} | Sum: {sum_val:>10.3f}{diff}")
            prev_sum = sum_val
        
        print("\n" + "=" * 70)
        
        # Now check for the spike in long-term statistics
        cursor.execute("""
            SELECT datetime(start_ts, 'unixepoch', 'localtime') as time, 
                   state, sum
            FROM statistics 
            WHERE metadata_id = ? 
            AND start_ts > strftime('%s', datetime('now', '-2 days'))
            ORDER BY start_ts DESC 
            LIMIT 10
        """, (meta_id,))
        
        long_rows = cursor.fetchall()
        
        if long_rows:
            print("\nLong-Term Statistics (Last 10):")
            print("=" * 70)
            for r in long_rows:
                print(f"{r[0]} | State: {r[1]:>10.3f} | Sum: {r[2]:>10.3f}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_transition_spike()
