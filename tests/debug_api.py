import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from getpass import getpass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
_LOGGER = logging.getLogger(__name__)

# Constants
BASE_URL = "https://api-mojlicznik.energa-operator.pl/dp"
LOGIN_ENDPOINT = "/apihelper/UserLogin"
SESSION_ENDPOINT = "/apihelper/SessionStatus"
DATA_ENDPOINT = "/resources/user/data"
CHART_ENDPOINT = "/resources/mchart"

HEADERS = {
    "User-Agent": "Energa/3.1.2 (pl.energa-operator.mojlicznik; build:1; iOS 16.6.1) Alamofire/5.6.4",
    "Accept": "application/json",
    "Accept-Language": "pl-PL;q=1.0, en-PL;q=0.9",
    "Content-Type": "application/json"
}

class EnergaAPI:
    def __init__(self, username, password, session):
        self._username = username
        self._password = password
        self._session = session
        self._token = None

    async def login(self):
        try:
            _LOGGER.info("Checking session status...")
            await self._session.get(f"{BASE_URL}{SESSION_ENDPOINT}", headers=HEADERS, ssl=False)
            
            params = {
                "clientOS": "ios", 
                "notifyService": "APNs", 
                "username": self._username, 
                "password": self._password
            }
            
            _LOGGER.info("Attempting login...")
            async with self._session.get(f"{BASE_URL}{LOGIN_ENDPOINT}", headers=HEADERS, params=params, ssl=False) as resp:
                if resp.status != 200:
                    _LOGGER.error(f"Login failed: HTTP {resp.status}")
                    return False
                
                try:
                    data = await resp.json()
                except:
                    _LOGGER.error("Login failed: Invalid JSON response")
                    return False

                _LOGGER.info(f"Login response data: {json.dumps(data)}")
                self._token = data.get("token") or (data.get("response") or {}).get("token")
                
                if self._token:
                    _LOGGER.info("Login successful! Token received.")
                else:
                    _LOGGER.warning("Login returned success but NO TOKEN. Attempting to proceed with cookies only...")
                    for cookie in self._session.cookie_jar:
                        _LOGGER.info(f"Cookie: {cookie.key}={cookie.value}")

                return True

        except Exception as e:
            _LOGGER.error(f"Login exception: {e}")
            return False

    async def get_meters(self):
        _LOGGER.info("Fetching meters...")
        data = await self._api_get(DATA_ENDPOINT)
        if not data:
            return []
        
        if not data.get("response"):
            _LOGGER.warning("No 'response' field in get_meters data")
            return []

        meters = data["response"].get("meterPoints", [])
        _LOGGER.info(f"Found {len(meters)} meter points.")
        return meters

    async def get_chart(self, meter_id, obis, date_obj):
        ts = int(date_obj.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        params = {
            "meterPoint": meter_id,
            "type": "DAY",
            "meterObject": obis,
            "mainChartDate": str(ts)
        }
        
        _LOGGER.info(f"Fetching chart for {date_obj.date()} (meter={meter_id}, obis={obis})...")
        data = await self._api_get(CHART_ENDPOINT, params=params)
        
        if data and data.get("response") and data["response"].get("mainChart"):
            points = data["response"]["mainChart"]
            _LOGGER.info(f"Received {len(points)} data points for {date_obj.date()}")
            return points
        else:
            _LOGGER.warning(f"No chart data for {date_obj.date()}. Response: {json.dumps(data)[:200]}...")
            return []

    async def _api_get(self, path, params=None):
        url = f"{BASE_URL}{path}"
        final_params = params.copy() if params else {}
        if self._token and "token" not in final_params:
            final_params["token"] = self._token
            
        try:
            async with self._session.get(url, headers=HEADERS, params=final_params, ssl=False) as resp:
                if resp.status != 200:
                    _LOGGER.error(f"API Error {resp.status} for {url}")
                    text = await resp.text()
                    _LOGGER.error(f"Response body: {text}")
                    return None
                return await resp.json()
        except Exception as e:
            _LOGGER.error(f"Request failed: {e}")
            return None

async def main():
    print("\n--- Energa API Debug Tool ---\n")
    username = input("Username: ").strip()
    password = getpass("Password: ").strip()
    
    if not username or not password:
        print("Credentials required.")
        return

    async with aiohttp.ClientSession() as session:
        api = EnergaAPI(username, password, session)
        
        if await api.login():
            meters = await api.get_meters()
            
            for i, m in enumerate(meters):
                mid = m.get("id")
                alias = m.get("ppe") or m.get("dev") or "Unknown"
                print(f"\nMeter #{i+1}: ID={mid}, Alias={alias}")
                print(f"Full Meter Data: {json.dumps(m, indent=2)}")
                
                # Check for OBIS codes
                obis_plus = None
                obis_minus = None
                for obj in m.get("meterObjects", []):
                    code = obj.get("obis", "")
                    if code.startswith("1-0:1.8.0"): obis_plus = code
                    elif code.startswith("1-0:2.8.0"): obis_minus = code
                
                print(f"OBIS Import (Pobór): {obis_plus}")
                print(f"OBIS Export (Oddawanie): {obis_minus}")

                # Check history for last 3 days
                for days_ago in range(3):
                    date_check = datetime.now() - timedelta(days=days_ago)
                    
                    if obis_plus:
                        data = await api.get_chart(mid, obis_plus, date_check)
                        if data:
                            vals = [p.get("zones", [0])[0] for p in data]
                            print(f"  Date {date_check.date()} Import: Sum={sum(filter(None, vals)):.2f} kWh, Points={len(vals)}")
                            print(f"    Raw Sample (first 3): {vals[:3]}")

                    if obis_minus:
                        data = await api.get_chart(mid, obis_minus, date_check)
                        if data:
                            vals = [p.get("zones", [0])[0] for p in data]
                            print(f"  Date {date_check.date()} Export: Sum={sum(filter(None, vals)):.2f} kWh, Points={len(vals)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted.")
