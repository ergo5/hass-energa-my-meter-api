"""Check why Energa integration has no entities after restart"""

import requests

HA_URL = "http://192.168.70.199:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3MTQ5ZWJiZTg0OWM0ZmE3OTBlOGFmNGZiOTlmNDg5NiIsImlhdCI6MTc2NjY4MzcyMCwiZXhwIjoyMDgyMDQzNzIwfQ.QL2li2QXirbu7UaSBuZadZVK34NHOqAKeZ-BJAPGGRc"

headers = {"Authorization": f"Bearer {TOKEN}"}

print("Checking integration status...")

# Get all states
response = requests.get(f"{HA_URL}/api/states", headers=headers)
all_states = response.json()

print(f"\nTotal entities: {len(all_states)}")

# Search for energa
energa = [e for e in all_states if "energa" in e["entity_id"].lower()]
print(f"Energa entities: {len(energa)}")

if energa:
    for e in energa[:5]:
        print(f"  {e['entity_id']}: {e['state']}")
else:
    # Check config entries
    response = requests.get(
        f"{HA_URL}/api/config/config_entries/entry", headers=headers
    )
    if response.status_code == 200:
        entries = response.json()
        energa_entry = [e for e in entries if e.get("domain") == "energa_mobile"]
        if energa_entry:
            print("\n✅ Energa integration config entry exists:")
            for entry in energa_entry:
                print(f"  Entry ID: {entry.get('entry_id')}")
                print(f"  Title: {entry.get('title')}")
                print(f"  State: {entry.get('state')}")
                print(f"  Disabled: {entry.get('disabled_by')}")
        else:
            print("\n❌ No Energa integration config entry found")

    # Check error log
    print("\nChecking error log for Energa...")
    response = requests.get(f"{HA_URL}/api/error_log", headers=headers)
    log = response.text

    energa_errors = [
        line for line in log.split("\n")[-200:] if "energa" in line.lower()
    ]
    if energa_errors:
        print("Found Energa errors:")
        for err in energa_errors[-10:]:
            print(f"  {err}")
    else:
        print("No Energa errors in log")
