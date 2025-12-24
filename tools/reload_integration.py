#!/usr/bin/env python3
"""Reload Energa integration via HA API"""
import urllib.request
import json

HA_URL = "http://192.168.70.199:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjZjVlMGY3MDdlYmU0N2QyYmU0NmQ4YTQzMzdjOTY0MiIsImlhdCI6MTc2NjU2MDczOCwiZXhwIjoyMDgxOTIwNzM4fQ.4Q0QyBhbORMI9KMaw4DsjuX8bJtKU8JxA-9qkeyXYA8"

def reload_integration():
    data = json.dumps({"entity_id": "sensor.energa_30132815_zuzycie_dzis"}).encode()
    req = urllib.request.Request(
        f"{HA_URL}/api/services/homeassistant/reload_config_entry",
        data=data,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Reload: {resp.status}")
    except Exception as e:
        print(f"Reload failed: {e}")
        # Fallback - reload all custom components
        req2 = urllib.request.Request(
            f"{HA_URL}/api/services/homeassistant/reload_custom_templates",
            headers={"Authorization": f"Bearer {TOKEN}"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req2) as resp:
                print(f"Reload templates: {resp.status}")
        except:
            pass

if __name__ == "__main__":
    reload_integration()
