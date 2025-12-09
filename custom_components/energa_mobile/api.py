"""API Client for Energa Mobile."""
import logging
import aiohttp
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from .const import BASE_URL, LOGIN_ENDPOINT, DATA_ENDPOINT, HEADERS, HISTORY_ENDPOINT, MO_CONSUMPTION, MO_PRODUCTION

_LOGGER = logging.getLogger(__name__)

class EnergaAuthError(Exception):
    """Błąd logowania."""
    pass

class EnergaConnectionError(Exception):
    """Błąd połączenia."""
    pass

class EnergaAPI:
    def __init__(self, username, password, token, session: aiohttp.ClientSession):
        self._username = username
        self._password = password
        self._token = token
        self._session = session

    async def async_login(self):
        """Logowanie do API."""
        params = {
            "clientOS": "ios",
            "notifyService": "APNs",
            "username": self._username,
            "password": self._password,
            "token": self._token
        }
        try:
            async with self._session.get(f"{BASE_URL}{LOGIN_ENDPOINT}", headers=HEADERS, params=params, ssl=False) as resp:
                if resp.status != 200:
                    _LOGGER.error(f"Login failed: {resp.status}")
                    raise EnergaAuthError
                try:
                    data = await resp.json()
                    if data.get("success") is False: raise EnergaAuthError
                except: pass
                return True
        except aiohttp.ClientError as err: raise EnergaConnectionError from err

    async def async_get_data(self):
        """Pobranie danych."""
        try: data = await self._fetch_and_parse()
        except EnergaAuthError:
            _LOGGER.warning("Token expired. Relogging...")
            await self.async_login()
            data = await self._fetch_and_parse()
        
        meter_id = data.get("meter_id") 
        if meter_id:
            # === FIX CZASU: WARSZAWA ===
            # Wyliczamy północ dla polskiej strefy czasowej
            tz_warsaw = ZoneInfo("Europe/Warsaw")
            now_warsaw = datetime.now(tz_warsaw)
            today_midnight = now_warsaw.replace(hour=0, minute=0, second=0, microsecond=0)
            timestamp = int(today_midnight.timestamp() * 1000)

            _LOGGER.debug(f"Requesting Meter: {meter_id}, Timestamp: {timestamp}")

            # 1. Pobór (OBIS Import)
            try:
                cons_data = await self._fetch_chart_data(meter_id, timestamp, MO_CONSUMPTION)
                data["daily_pobor"] = self._sum_chart_values(cons_data)
            except Exception as e: _LOGGER.error(f"Error import: {e}")

            # 2. Produkcja (OBIS Export)
            try:
                prod_data = await self._fetch_chart_data(meter_id, timestamp, MO_PRODUCTION)
                data["daily_produkcja"] = self._sum_chart_values(prod_data)
            except Exception as e: _LOGGER.error(f"Error export: {e}")

        return data

    async def _fetch_chart_data(self, meter_id, timestamp, mo_type):
        """Pobiera dane wykresu - RĘCZNE BUDOWANIE URL (RAW)."""
        
        # === FIX URL ===
        # Standardowe 'params={...}' w aiohttp koduje dwukropek na %3A.
        # Stary serwer Energi tego nie obsługuje i zwraca błędne dane.
        # Budujemy URL ręcznie, aby wysłać czysty kod OBIS.
        
        url = f"{BASE_URL}{HISTORY_ENDPOINT}?mainChartDate={timestamp}&meterPoint={meter_id}&type=DAY&mo={mo_type}"
        
        # _LOGGER.debug(f"Fetching RAW URL: {url}") # Odkomentuj w razie problemów

        async with self._session.get(url, headers=HEADERS, ssl=False) as resp:
            if resp.status in [401, 403]: raise EnergaAuthError
            if resp.status != 200: return None
            return await resp.json()

    def _sum_chart_values(self, json_data):
        total = 0.0
        try:
            if json_data and "response" in json_data and "mainChart" in json_data["response"]:
                for point in json_data["response"]["mainChart"]:
                    if "zones" in point and point["zones"]:
                        hourly_sum = sum(val for val in point["zones"] if val is not None)
                        total += hourly_sum
        except: pass
        return round(total, 3)

    async def _fetch_and_parse(self):
        async with self._session.get(f"{BASE_URL}{DATA_ENDPOINT}", headers=HEADERS, ssl=False) as resp:
            if resp.status in [401, 403]: raise EnergaAuthError
            if resp.status != 200: raise EnergaConnectionError
            data = await resp.json()
            return self._parse_json(data)

    def _parse_json(self, json_data):
        try:
            response = json_data['response']
            meter_point = response['meterPoints'][0]
            measurements = meter_point['lastMeasurements']
            agreement = response.get('agreementPoints', [{}])[0]
            dealer = agreement.get('dealer', {})
            result = {
                "meter_id": meter_point.get('id'),
                "pobor": None, "produkcja": None,
                "ppe": meter_point.get('dev'), "tariff": meter_point.get('tariff'),
                "address": agreement.get('address'), "seller": dealer.get('name'),
                "contract_date": str(dealer.get('start')),
                "daily_pobor": 0.0, "daily_produkcja": 0.0
            }
            # Dane "Total" (z liczników) jako backup
            for m in measurements:
                if "A+" in m.get('zone', ''): result["pobor"] = float(m.get('value', 0))
                if "A-" in m.get('zone', ''): result["produkcja"] = float(m.get('value', 0))
            return result
        except: return None