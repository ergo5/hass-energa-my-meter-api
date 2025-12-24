#!/usr/bin/env python3
"""HA API Test Script - LAB Access"""
import urllib.request
import json

HA_URL = "http://192.168.70.199:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjZjVlMGY3MDdlYmU0N2QyYmU0NmQ4YTQzMzdjOTY0MiIsImlhdCI6MTc2NjU2MDczOCwiZXhwIjoyMDgxOTIwNzM4fQ.4Q0QyBhbORMI9KMaw4DsjuX8bJtKU8JxA-9qkeyXYA8"

def ha_get(endpoint):
    req = urllib.request.Request(
        f"{HA_URL}/api/{endpoint}",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def main():
    print("=== HA API Test ===")
    
    # Test API
    status = ha_get("")
    print(f"API: {status.get('message', 'OK')}")
    
    # Get Energa entities
    states = ha_get("states")
    energa = [e for e in states if "energa" in e["entity_id"].lower()]
    
    print(f"\nEnerga entities: {len(energa)}")
    for e in energa:
        print(f"  {e['entity_id']}: {e['state']}")
    
    # Get attributes of first sensor
    if energa:
        for e in energa:
            if "zuzycie_dzis" in e["entity_id"]:
                print(f"\nAttributes of {e['entity_id']}:")
                for k, v in e.get("attributes", {}).items():
                    print(f"  {k}: {v}")
                break

if __name__ == "__main__":
    main()
