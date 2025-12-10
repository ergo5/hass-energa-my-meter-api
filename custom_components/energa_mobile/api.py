"""API Client for Energa Mobile v2.1.0."""
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
    def __init__(self, username, password, session: aiohttp.ClientSession):
        self._username = username
        self._password = password
        self._session = session
        self._token = None
        self._meter_data = None # Cache metadanych (ID, OBIS)

    async def async_login(self):
        """Logowanie z obsługą Ciasteczek i Tokena."""
        try:
            # 1. Inicjalizacja sesji
            await self._api_get(SESSION_ENDPOINT)
            
            # 2. Logowanie
            params = {
                "clientOS": "ios",
                "notifyService": "APNs",
                "username": self._username,
                "password": self._password
            }
            
            url = f"{BASE_URL}{LOGIN_ENDPOINT}"
            async with self._session.get(url, headers=HEADERS, params=params, ssl=False) as resp:
                if resp.status != 200:
                    raise EnergaConnectionError(f"Login HTTP Error: {resp.status}")
                
                try:
                    data = await resp.json()
                except:
                    raise EnergaConnectionError("Invalid JSON response during login")

                if not data.get("success"):
                    _LOGGER.error(f"Login failed: {data}")
                    raise EnergaAuthError("Invalid credentials")
                
                # Próba wyciągnięcia tokena (jeśli jest, to super, jak nie - działamy na cookies)
                self._token = data.get("token")
                if not self._token and data.get("response"):
                    self._token = data.get("response").get("token")
                
                return True

        except aiohttp.ClientError as err:
            raise EnergaConnectionError from err

    async def async_get_data(self):
        """Pobiera dane dzienne (licznikowe + wykresy)."""
        try:
            # Pobierz metadane jeśli ich nie ma (pierwsze uruchomienie)
            if not self._meter_data:
                self._meter_data = await self._fetch_user_metadata()
            
            # Oblicz północ dla bieżącego dnia
            tz_warsaw = ZoneInfo("Europe/Warsaw")
            now = datetime.now(tz_warsaw)
            midnight_ts = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)

            data = self._meter_data.copy()
            
            # 1. Wykres Poboru (A+) - sumowanie godzin
            if data.get("obis_plus"):
                vals = await self._fetch_chart(data["meter_point_id"], data["obis_plus"], midnight_ts)
                data["daily_pobor"] = sum(vals)
            else:
                data["daily_pobor"] = 0.0
            
            # 2. Wykres Produkcji (A-) - sumowanie godzin
            if data.get("obis_minus"):
                vals = await self._fetch_chart(data["meter_point_id"], data["obis_minus"], midnight_ts)
                data["daily_produkcja"] = sum(vals)
            else:
                data["daily_produkcja"] = 0.0

            return data

        except EnergaAuthError:
            _LOGGER.info("Session expired. Re-logging...")
            await self.async_login()
            # Po przelogowaniu odświeżamy metadane, bo mogły wygasnąć
            self._meter_data = await self._fetch_user_metadata()
            return await self.async_get_data()

    async def _fetch_user_metadata(self):
        """Wykrywa kody OBIS z API."""
        json_data = await self._api_get(DATA_ENDPOINT)
        
        if not json_data.get("response"):
            raise EnergaConnectionError("Empty response from user data")

        mp = json_data["response"]["meterPoints"][0]
        ag = json_data["response"].get("agreementPoints", [{}])[0]

        result = {
            "meter_point_id": mp.get("id"),
            "ppe": mp.get("dev"),
            "tariff": mp.get("tariff"),
            "address": ag.get("address"),
            # Wartości domyślne
            "daily_pobor": 0.0,
            "daily_produkcja": 0.0,
            "total_plus": 0.0,
            "total_minus": 0.0,
            "obis_plus": None,
            "obis_minus": None
        }

        # Stany licznika (Totals)
        for m in mp.get("lastMeasurements", []):
            zone = m.get("zone", "")
            if "A+" in zone: result["total_plus"] = float(m.get("value", 0))
            if "A-" in zone: result["total_minus"] = float(m.get("value", 0))

        # Detekcja OBIS (Klucz do sukcesu)
        for obj in mp.get("meterObjects", []):
            obis = obj.get("obis", "")
            if obis.startswith("1-0:1.8.0"): result["obis_plus"] = obis
            elif obis.startswith("1-0:2.8.0"): result["obis_minus"] = obis

        return result

    async def _fetch_chart(self, meter_id, obis, timestamp):
        """Pobiera wykres dla konkretnego kodu OBIS."""
        params = {
            "meterPoint": meter_id,
            "type": "DAY",
            "meterObject": obis,
            "mainChartDate": str(timestamp)
        }
        if self._token: params["token"] = self._token
            
        data = await self._api_get(CHART_ENDPOINT, params=params)
        
        try:
            values = []
            for point in data["response"]["mainChart"]:
                zones = point.get("zones", [])
                val = zones[0] if zones and zones[0] is not None else 0.0
                values.append(val)
            return values
        except: return []

    async def _api_get(self, path, params=None):
        url = f"{BASE_URL}{path}"
        final_params = params.copy() if params else {}
        # Dodajemy token tylko jeśli go mamy (fallback do cookies)
        if self._token and "token" not in final_params:
             final_params["token"] = self._token

        async with self._session.get(url, headers=HEADERS, params=final_params, ssl=False) as resp:
            if resp.status == 401: raise EnergaAuthError
            resp.raise_for_status()
            return await resp.json()