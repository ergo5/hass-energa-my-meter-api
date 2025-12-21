"""Clean up old Energa statistics from Lab HA database before v3.7 deployment."""
import sqlite3
import os

DB_PATH = r"y:\home-assistant_v2.db"

def cleanup_energa_statistics():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return False
    
    print("=" * 70)
    print("  Energa v3.7: Clean Slate - Removing Old Statistics")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Find all Energa-related statistics
        cursor.execute("""
            SELECT id, statistic_id FROM statistics_meta 
            WHERE statistic_id LIKE '%energa%'
        """)
        
        energa_stats = cursor.fetchall()
        
        if not energa_stats:
            print("\n✓ No Energa statistics found. Database already clean!")
            return True
        
        print(f"\n📊 Found {len(energa_stats)} Energa statistics sensors:")
        for stat_id, stat_name in energa_stats:
            print(f"   - {stat_name}")
        
        # Delete statistics data
        deleted_short = 0
        deleted_long = 0
        
        for meta_id, stat_name in energa_stats:
            cursor.execute("DELETE FROM statistics_short_term WHERE metadata_id = ?", (meta_id,))
            deleted_short += cursor.rowcount
            
            cursor.execute("DELETE FROM statistics WHERE metadata_id = ?", (meta_id,))
            deleted_long += cursor.rowcount
        
        # Delete metadata
        cursor.execute("DELETE FROM statistics_meta WHERE statistic_id LIKE '%energa%'")
        deleted_meta = cursor.rowcount
        
        conn.commit()
        
        print(f"\n✅ SUCCESS: Deleted Energa statistics:")
        print(f"   - Metadata: {deleted_meta} sensors")
        print(f"   - Short-term data: {deleted_short} rows")
        print(f"   - Long-term data: {deleted_long} rows")
        print(f"\n💡 v3.7 will create fresh sensors with new architecture.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = cleanup_energa_statistics()
    exit(0 if success else 1)
