
import asyncio
import logging
from datetime import date, datetime
from typing import Any

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def run_wide_simulation():
    print("==========================================")
    print("   SIMULATION SUITE: WIDE & ROBUST       ")
    print("   Target: ALL DATA TYPES                ")
    print("==========================================")

    # --- LOGIC UNDER TEST (Simulating sensor.py native_value) ---
    def simulate_native_value(val: Any, restored_value: Any = None) -> Any:
        # LOGIC:
        if val is not None:
             # ZERO-GUARD logic
             try:
                 f_val = float(val)
                 # Logic continues if float conversion succeeds...
                 if f_val <= 0 and restored_value:
                      try:
                          prev_f = float(restored_value)
                          if prev_f > 100:
                               print(f"      🛡️ GUARD: Blocking {val} (Prev: {restored_value})")
                               return restored_value
                      except (ValueError, TypeError): pass
             except (ValueError, TypeError):
                 # This is where 'date' objects should fall through
                 print(f"      ℹ️  Non-numeric type detected ({type(val).__name__}). Skipping Guard.")
                 pass

             return val
        
        return restored_value

    # --- TEST CASES ---
    test_cases = [
        ("Numeric Normal", 1001.0, 1000.0, 1001.0),
        ("Numeric Zero (Glitch)", 0.0, 1000.0, 1000.0), # Should return restored
        ("Numeric Negative", -5.0, 1000.0, 1000.0),    # Should return restored
        ("String Normal", "G11", "G11", "G11"),
        ("String Zero-Like", "0", "1000", "1000"),     # Should Block string "0" too!
        ("Date Object (Contract)", date(2025, 6, 11), None, date(2025, 6, 11)),
        ("None", None, 123.0, 123.0)
    ]

    failures = 0
    
    for name, input_val, restored, expected in test_cases:
        print(f"\n[TEST] {name}")
        print(f"   Input: {input_val} ({type(input_val).__name__})")
        
        try:
            result = simulate_native_value(input_val, restored)
            print(f"   Result: {result}")
            
            if result == expected:
                print("   ✅ PASS")
            else:
                print(f"   ❌ FAIL (Expected {expected}, Got {result})")
                failures += 1
                
        except Exception as e:
            print(f"   🔥 CRASH: {type(e).__name__}: {e}")
            failures += 1

    print("\n==========================================")
    if failures == 0:
        print("   🏆 STATUS: ROBUST. All types handled.")
    else:
        print(f"   💀 STATUS: FAILED ({failures} errors).")
    print("==========================================")

if __name__ == "__main__":
    run_wide_simulation()
