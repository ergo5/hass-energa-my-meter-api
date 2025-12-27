"""
Test script to explore Energa API - searching for OBIS codes for real-time power data

Target OBIS codes:
- 1.7.0: Instant active power (consumption)
- 2.7.0: Instant active power (feed-in - solar)
- 1.6.1: Maximum power in current period
- 31.7.0/51.7.0/71.7.0: Current (phases L1, L2, L3)
- 32.7.0/52.7.0/72.7.0: Voltage (phases L1, L2, L3)
"""

import asyncio
import json
from pathlib import Path

import aiohttp

# Energa API configuration
BASE_URL = "https://mojlicznik.energa-operator.pl"
SESSION_ENDPOINT = "/dp/UserManager.mvc/GetUserDataToSession"
LOGIN_ENDPOINT = "/dp/UserManager.mvc/CommonLoginMobile"
DATA_ENDPOINT = "/moj-licznik-web-api/dane/"
CHART_ENDPOINT = "/moj-licznik-web-api/wykresy/godzinowy"
HEADERS = {"accept": "application/json", "content-type": "application/json"}

# Target OBIS codes we're looking for
TARGET_OBIS = {
    "1.7.0": "Instant active power (consumption)",
    "2.7.0": "Instant active power (feed-in - solar)",
    "1.6.1": "Maximum power in current period",
    "31.7.0": "Current phase L1",
    "51.7.0": "Current phase L2",
    "71.7.0": "Current phase L3",
    "32.7.0": "Voltage phase L1",
    "52.7.0": "Voltage phase L2",
    "72.7.0": "Voltage phase L3",
}


class EnergaAuthError(Exception):
    pass


class EnergaConnectionError(Exception):
    pass


def read_credentials():
    """Read credentials from .lab_credentials file"""
    creds_file = Path(".lab_credentials")
    if not creds_file.exists():
        return None, None

    username = None
    password = None
    for line in creds_file.read_text().splitlines():
        if line.startswith("ENERGA_USERNAME="):
            username = line.split("=", 1)[1].strip()
        elif line.startswith("ENERGA_PASSWORD="):
            password = line.split("=", 1)[1].strip()

    return username, password


def search_obis_in_data(data, path=""):
    """Recursively search for OBIS codes in JSON data"""
    found = []

    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            # Check if key or value contains OBIS pattern
            if isinstance(key, str):
                for obis_code in TARGET_OBIS.keys():
                    if obis_code.replace(".", "") in key or obis_code in key:
                        found.append(
                            {
                                "obis_code": obis_code,
                                "description": TARGET_OBIS[obis_code],
                                "path": current_path,
                                "key": key,
                                "value": value,
                            }
                        )

            # Recurse into nested structures
            found.extend(search_obis_in_data(value, current_path))

    elif isinstance(data, list):
        for idx, item in enumerate(data):
            current_path = f"{path}[{idx}]"
            found.extend(search_obis_in_data(item, current_path))

    return found


async def test_api():
    """Explore API for OBIS codes"""

    username, password = read_credentials()
    if not username or not password:
        print("❌ Could not read credentials from .lab_credentials")
        print("   Please add: ENERGA_USERNAME=your@email.com")
        print("               ENERGA_PASSWORD=yourpassword")
        return

    print(f"📝 Using credentials from .lab_credentials: {username}")

    async with aiohttp.ClientSession() as session:
        print("\n" + "=" * 80)
        print("🔍 SEARCHING FOR OBIS REAL-TIME POWER DATA")
        print("=" * 80)

        print("\n📋 Target OBIS codes:")
        for code, desc in TARGET_OBIS.items():
            print(f"   {code}: {desc}")

        try:
            obis_found = []  # Initialize here

            # Login
            print("\n[1/5] Logging in...")
            await session.get(
                f"{BASE_URL}{SESSION_ENDPOINT}", headers=HEADERS, ssl=False
            )

            params = {
                "clientOS": "ios",
                "notifyService": "APNs",
                "username": username,
                "password": password,
                "token": "obis_search_token",
            }
            async with session.get(
                f"{BASE_URL}{LOGIN_ENDPOINT}", headers=HEADERS, params=params, ssl=False
            ) as resp:
                if resp.status != 200:
                    raise EnergaConnectionError(f"Login failed: HTTP {resp.status}")
                data = await resp.json()
                if not data.get("success"):
                    raise EnergaAuthError("Invalid credentials")
                print("✅ Login successful!")

            # Get main meter data
            print("\n[2/5] Fetching main meter data...")
            async with session.get(
                f"{BASE_URL}{DATA_ENDPOINT}", headers=HEADERS, ssl=False
            ) as resp:
                all_data = await resp.json()

            print("✅ Got API response")

            # Search for OBIS codes
            print("\n[3/5] Searching for OBIS codes in response...")
            obis_found = search_obis_in_data(all_data)

            if obis_found:
                print(f"✅ FOUND {len(obis_found)} OBIS CODE REFERENCES!")
                for item in obis_found:
                    print(f"\n   🎯 {item['obis_code']}: {item['description']}")
                    print(f"      Path: {item['path']}")
                    print(f"      Key: {item['key']}")
                    print(f"      Value: {item['value']}")
            else:
                print("❌ No OBIS codes found in main data response")

            # Check meters array
            meters = all_data.get("punktyPoboru", [])
            if meters:
                print(
                    f"\n[4/5] Checking {len(meters)} meter(s) for power-related fields..."
                )

                for idx, meter in enumerate(meters, 1):
                    print(f"\n   📟 Meter {idx}: {meter.get('numerLicznika', 'N/A')}")

                    # Look for power/voltage/current fields
                    power_related = {}
                    for key, value in meter.items():
                        key_lower = key.lower()
                        if any(
                            word in key_lower
                            for word in [
                                "moc",
                                "power",
                                "voltage",
                                "napięcie",
                                "prąd",
                                "current",
                                "watt",
                                "volt",
                                "amp",
                            ]
                        ):
                            power_related[key] = value

                    if power_related:
                        print("      Power-related fields found:")
                        for k, v in power_related.items():
                            print(f"         {k}: {v}")
                    else:
                        print("      ❌ No obvious power fields")

            # Try potential OBIS-specific endpoints
            print("\n[5/5] Trying potential OBIS/power endpoints...")
            if meters:
                meter_id = meters[0].get("idPpe")
                if meter_id:
                    endpoints = [
                        f"/moj-licznik-web-api/obis/{meter_id}",
                        f"/moj-licznik-web-api/power/{meter_id}",
                        f"/moj-licznik-web-api/realtime/{meter_id}",
                        f"/dp/Obis.mvc/GetData?idPpe={meter_id}",
                        f"/dp/Power.mvc/GetLiveData?idPpe={meter_id}",
                    ]

                    for endpoint in endpoints:
                        try:
                            url = f"{BASE_URL}{endpoint}"
                            async with session.get(
                                url,
                                headers=HEADERS,
                                ssl=False,
                                timeout=aiohttp.ClientTimeout(total=3),
                            ) as resp:
                                if resp.status == 200:
                                    obis_data = await resp.json()
                                    print(f"\n   ✅ FOUND ENDPOINT: {endpoint}")
                                    print("      Response preview:")
                                    print(
                                        f"      {json.dumps(obis_data, indent=2, ensure_ascii=False)[:500]}"
                                    )

                                    # Search this response for OBIS
                                    found_in_endpoint = search_obis_in_data(obis_data)
                                    if found_in_endpoint:
                                        print("\n      🎯 OBIS codes in this endpoint:")
                                        for item in found_in_endpoint:
                                            print(
                                                f"         {item['obis_code']}: {item['value']}"
                                            )
                        except:
                            pass

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback

            traceback.print_exc()

        print("\n" + "=" * 80)
        print("SEARCH COMPLETE")
        print("=" * 80)

        if obis_found:
            print(f"\n✅ SUCCESS: Found {len(obis_found)} OBIS code references")
            print("   We can implement these as new real-time sensors!")
        else:
            print("\n❌ No OBIS codes found in current API endpoints")
            print("   Real-time power data may not be available via this API")


if __name__ == "__main__":
    asyncio.run(test_api())
