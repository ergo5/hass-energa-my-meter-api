"""API Client for Energa Mobile v2.0."""
import logging
import aiohttp
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from .const import BASE_URL, LOGIN_ENDPOINT, SESSION_ENDPOINT, DATA_ENDPOINT, CHART_ENDPOINT, HEADERS

_LOGGER = logging.getLogger(__name__)

class EnergaAuthError(Exception): pass
class EnergaConnectionError(Exception): pass

class EnergaAPI:
    def __init__(self, username, password, token, session: aiohttp.ClientSession):
        self._username = username
        self._password = password
        self._token = token
        self._session = session
        
        # Cache na dane o liczniku (żeby nie pobierać /user/data co chwilę)
        self._meter_data = None

    async def async_login(self):
        """Logowanie dokładnie jak w skrypcie."""
        try:
            # 1. SessionStatus
            await self._api_get(SESSION_ENDPOINT)
            
            # 2. UserLogin
            params = {
                "clientOS": "ios",
                "notifyService": "APNs",
                "username": self._username,
                "password": self._password,
                "token": self._token
            }
            data = await self._api_get(LOGIN_ENDPOINT, params=params)
            
            if not data.get("success"):
                _LOGGER.error(f"Login failed response: {data}")
                raise EnergaAuthError("Login failed")
            
            return True
        except aiohttp.ClientError as err:
            raise EnergaConnectionError from err

    async def async_get_data(self):
        """Główna metoda pobierająca dane."""
        try:
            # Jeśli nie mamy danych o liczniku (ID, kody OBIS), pobierz je
            if not self._meter_data:
                self._meter_data = await self._fetch_user_metadata()
            
            # Upewnij się, że mamy timestamp dla północy w Warszawie
            tz_warsaw = ZoneInfo("Europe/Warsaw")
            now = datetime.now(tz_warsaw)
            midnight_ts = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)

            # Pobieramy dane
            data = self._meter_data.copy() # Kopia słownika z metadanymi
            
            # 1. Wykres Poboru (A+)
            if data.get("obis_plus"):
                hourly_plus = await self._fetch_chart(data["meter_point_id"], data["obis_plus"], midnight_ts)
                data["daily_pobor"] = sum(hourly_plus)
            else:
                data["daily_pobor"] = 0.0

            # 2. Wykres Produkcji (A-)
            if data.get("obis_minus"):
                hourly_minus = await self._fetch_chart(data["meter_point_id"], data["obis_minus"], midnight_ts)
                data["daily_produkcja"] = sum(hourly_minus)
            else:
                data["daily_produkcja"] = 0.0

            return data

        except EnergaAuthError:
            # Jeśli token wygasł, spróbuj zalogować się ponownie i powtórzyć
            _LOGGER.info("Token expired, re-logging...")
            await self.async_login()
            self._meter_data = await self._fetch_user_metadata() # Odśwież metadata po logowaniu
            return await self.async_get_data() # Rekurencja (raz)

    async def _fetch_user_metadata(self):
        """Pobiera /user/data i wykrywa kody OBIS."""
        json_data = await self._api_get(DATA_ENDPOINT)
        resp = json_data.get("response", {})
        
        if not resp:
            raise EnergaConnectionError("Empty response from user data")

        mp = resp["meterPoints"][0]
        ag = resp.get("agreementPoints", [{}])[0]

        result = {
            "meter_point_id": mp.get("id"), # Tu będzie np. 300302
            "ppe": mp.get("dev"),
            "tariff": mp.get("tariff"),
            "address": ag.get("address"),
            "total_plus": 0.0,
            "total_minus": 0.0,
            "obis_plus": None,
            "obis_minus": None
        }

        # Totale z lastMeasurements
        for m in mp.get("lastMeasurements", []):
            zone = m.get("zone", "")
            if zone.startswith("A+"):
                result["total_plus"] = float(m.get("value", 0))
            elif zone.startswith("A-"):
                result["total_minus"] = float(m.get("value", 0))

        # Dynamiczne wykrywanie OBIS
        # To jest klucz do sukcesu z Twojego skryptu!
        for obj in mp.get("meterObjects", []):
            obis = obj.get("obis", "")
            if obis.startswith("1-0:1.8.0"): # Import (Pobór)
                result["obis_plus"] = obis
            elif obis.startswith("1-0:2.8.0"): # Export (Produkcja)
                result["obis_minus"] = obis

        _LOGGER.debug(f"Detected Metadata: {result}")
        return result

    async def _fetch_chart(self, meter_id, obis, timestamp_ms):
        """Pobiera wykres dla konkretnego kodu OBIS."""
        params = {
            "meterPoint": meter_id,
            "type": "DAY",
            "meterObject": obis, # Używamy pełnego kodu OBIS!
            "mainChartDate": str(timestamp_ms)
        }
        
        json_data = await self._api_get(CHART_ENDPOINT, params=params)
        
        try:
            main_chart = json_data["response"]["mainChart"]
            values = []
            for point in main_chart:
                zones = point.get("zones", [])
                # Bierzemy pierwszą strefę (całodobową) lub 0.0
                val = zones[0] if zones and zones[0] is not None else 0.0
                values.append(val)
            return values
        except (KeyError, IndexError, TypeError):
            _LOGGER.error(f"Error parsing chart data for {obis}")
            return []

    async def _api_get(self, path, params=None):
        """Pomocnicza metoda do zapytań."""
        url = f"{BASE_URL}{path}"
        async with self._session.get(url, headers=HEADERS, params=params, ssl=False) as resp:
            if resp.status == 401: # Token expired
                raise EnergaAuthError
            resp.raise_for_status()
            return await resp.json()