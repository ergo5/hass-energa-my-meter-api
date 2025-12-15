
import asyncio

# --- MOCKING THE SYSTEM ---

class MockAPI:
    def __init__(self):
        # 1. Start with CACHED data (Old state, e.g. from 1 hour ago)
        # Real life scenario: 24372 kWh
        self._meters_data = [{"meter_point_id": 300302, "meter_serial": "A123", "total_plus": 24372.0}]
        print(f"[INIT] API Cache initialized with OLD value: {self._meters_data[0]['total_plus']}")

    async def async_get_data(self, force_refresh: bool = False) -> list:
        print(f"\n[API Call] async_get_data called with force_refresh={force_refresh}")
        
        # 2. Logic from api.py (v3.6.0-beta.2)
        if force_refresh:
            print("  -> [Logic] Force Refresh is TRUE. Clearing cache.")
            self._meters_data = []
        else:
            print("  -> [Logic] Force Refresh is FALSE. Keeping cache if exists.")

        if not self._meters_data:
            print("  -> [Network] Fetching FRESH data from server...")
            # Real life scenario: 24385 kWh (Live state)
            self._meters_data = [{"meter_point_id": 300302, "meter_serial": "A123", "total_plus": 24385.0}]
            print(f"  -> [Network] Received NEW value: {self._meters_data[0]['total_plus']}")
        else:
            print(f"  -> [Cache] Returning CACHED value: {self._meters_data[0]['total_plus']}")
            
        return self._meters_data

async def simulate_import_logic(api, use_fix: bool):
    print(f"\n--- SIMULATION: Import {'WITH' if use_fix else 'WITHOUT'} FIX ---")
    
    # 3. Simulate the String ID "Crash" scenario
    meter_input = "300302" 
    print(f"[Import] Function received STRING ID: '{meter_input}'")

    # 4. Logic from __init__.py (Fail-Safe Block)
    if isinstance(meter_input, str):
        print("[Import] Activting Fail-Safe...")
        try:
            # THE CRITICAL DIFFERENCE
            if use_fix:
                # v3.6.0-beta.2 Logic
                ref_data = await api.async_get_data(force_refresh=True)
            else:
                # v3.5.25 Logic (The Bug)
                ref_data = await api.async_get_data(force_refresh=False)
                
            found = next((m for m in ref_data if str(m["meter_point_id"]) == str(meter_input)), None)
            
            if found:
                anchor = found["total_plus"]
                print(f"[RESULT] Import Anchor set to: {anchor}")
                
                # Math check
                live_value = 24385.0
                diff = live_value - anchor
                if diff > 0:
                     print(f"❌ FAILURE: Graph Drop detected! Graph is {diff} kWh below live reading.")
                else:
                     print(f"✅ SUCCESS: Graph matches live reading perfectly.")
            else:
                print("[Import] Failed to resolve ID.")
        except Exception as e:
            print(f"Error: {e}")

async def run_test():
    # Scenario 1: The Bug (v3.5.25 behavior)
    api_buggy = MockAPI()
    await simulate_import_logic(api_buggy, use_fix=False)

    # Scenario 2: The Fix (v3.6.0-beta.2 behavior)
    api_fixed = MockAPI()
    await simulate_import_logic(api_fixed, use_fix=True)

if __name__ == "__main__":
    asyncio.run(run_test())
