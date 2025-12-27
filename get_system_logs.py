#!/usr/bin/env python3
"""Get system logs from Home Assistant."""

import requests

HA_URL = "http://192.168.70.199:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3MTQ5ZWJiZTg0OWM0ZmE3OTBlOGFmNGZiOTlmNDg5NiIsImlhdCI6MTc2NjY4MzcyMCwiZXhwIjoyMDgyMDQzNzIwfQ.QL2li2QXirbu7UaSBuZadZVK34NHOqAKeZ-BJAPGGRc"

headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Get logger data via WebSocket simulation - use services endpoint
print("=== Fetching System Logs ===\n")

try:
    # Call system_log service to get logs
    response = requests.get(f"{HA_URL}/api/services", headers=headers, timeout=10)

    if response.status_code == 200:
        services = response.json()
        system_log_services = [s for s in services if s.get("domain") == "system_log"]
        print(f"Found {len(system_log_services)} system_log services")
        for svc in system_log_services:
            print(f"  - {svc.get('service')}")

    # Try to get error log through logbook
    print("\n=== Checking logbook for errors ===")
    response = requests.get(f"{HA_URL}/api/logbook", headers=headers, timeout=10)

    if response.status_code == 200:
        logbook = response.json()
        print(f"Logbook entries: {len(logbook)}")

        # Filter for energa-related entries
        energa_entries = [e for e in logbook if "energa" in str(e).lower()]
        print(f"Energa-related entries: {len(energa_entries)}")

        if energa_entries:
            print("\nRecent Energa logbook entries:")
            for entry in energa_entries[-5:]:
                print(
                    f"  {entry.get('when')}: {entry.get('name')} - {entry.get('message')}"
                )

    # Check websocket connection for live logs (not possible via REST)
    print("\n=== System Log Location ===")
    print("HA System logs are available at:")
    print(f"  WebUI: {HA_URL}/config/logs")
    print("  Or: Settings → System → Logs")

except Exception as e:
    print(f"Error: {e}")

print("\n=== Recommendation ===")
print("For detailed system logs, please open HA WebUI and go to:")
print("Settings → System → Logs")
print("Then filter by 'energa' to see integration-specific logs")
