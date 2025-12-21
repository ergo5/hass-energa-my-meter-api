import sqlite3
import os
from datetime import datetime

DB_PATH = r"y:\home-assistant_v2.db"

def repair_midnight_spike():
    """
    Repairs the statistics spike caused by the Source Switch in beta.19/20.
    
    The spike occurred because the sensor switched from lifetime counter values
    to daily values that reset at midnight, creating a massive negative delta.
    
    This script deletes all affected statistics rows after the midnight transition.
    """
    
    if not os.path.exists(DB_PATH):
        print(f"❌ ERROR: Database not found at {DB_PATH}")
        return False

    print("=" * 70)
    print("  Energa Mobile: Midnight Spike Repair (beta.19/20 Fix)")
    print("=" * 70)
    
    # Backup warning
    print("\n⚠️  WARNING: This script will modify the Home Assistant database.")
    print("   Make sure Home Assistant is stopped before proceeding!")
    print("   A backup of home-assistant_v2.db is recommended.\n")
    
    response = input("Continue? (type 'yes' to proceed): ")
    if response.lower() != 'yes':
        print("❌ Operation cancelled.")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Find the sensor
        cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = 'sensor.energa_import_panel_energia'")
        row = cursor.fetchone()
        if not row:
            print("❌ ERROR: sensor.energa_import_panel_energia not found!")
            return False
        
        meta_id = row[0]
        print(f"\n✓ Found sensor (metadata_id: {meta_id})")
        
        # Find the midnight transition timestamp (2025-12-21 00:00:00 in your timezone)
        # Convert to UTC epoch for SQLite
        transition_time = datetime(2025, 12, 21, 0, 0, 0).timestamp()
        
        # Count affected rows in short-term
        cursor.execute("""
            SELECT COUNT(*) FROM statistics_short_term 
            WHERE metadata_id = ? AND start_ts >= ?
        """, (meta_id, transition_time))
        short_count = cursor.fetchone()[0]
        
        # Count affected rows in long-term
       cursor.execute("""
            SELECT COUNT(*) FROM statistics 
            WHERE metadata_id = ? AND start_ts >= ?
        """, (meta_id, transition_time))
        long_count = cursor.fetchone()[0]
        
        print(f"\n📊 Statistics to delete:")
        print(f"   - Short-term: {short_count} rows")
        print(f"   - Long-term: {long_count} rows")
        
        if short_count == 0 and long_count == 0:
            print("\n✓ No affected statistics found. Database already clean!")
            return True
        
        # Delete from short-term
        cursor.execute("""
            DELETE FROM statistics_short_term 
            WHERE metadata_id = ? AND start_ts >= ?
        """, (meta_id, transition_time))
        
        # Delete from long-term
        cursor.execute("""
            DELETE FROM statistics 
            WHERE metadata_id = ? AND start_ts >= ?
        """, (meta_id, transition_time))
        
        conn.commit()
        
        print(f"\n✅ SUCCESS: Deleted {short_count + long_count} statistics rows.")
        print("   Home Assistant will rebuild these from live sensor data.")
        print("\n💡 Next steps:")
        print("   1. Update to beta.21 (which reverts the source switch)")
        print("   2. Restart Home Assistant")
        print("   3. The sensor will resume using the lifetime counter")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during repair: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = repair_midnight_spike()
    exit(0 if success else 1)
