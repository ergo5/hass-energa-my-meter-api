"""API Client for Energa Mobile."""
import logging
import aiohttp
import json
from datetime import datetime
from zoneinfo import ZoneInfo # Wymagane do poprawnej obsługi czasu w PL
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
            async with self._session.get(
                f"{BASE_URL}{LOGIN_ENDPOINT}", 
                headers=HEADERS, 
                params=params, 
                ssl=False 
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error(f"Login failed: {resp.status}")
                    raise EnergaAuthError
                try:
                    data = await resp.json()
                    if data.get("success") is False:
                        raise EnergaAuthError
                except Exception:
                    pass
                return True
        except aiohttp.ClientError as err:
            raise EnergaConnectionError from err

    async def async_get_data(self):
        """Pobranie danych."""
        try:
            data = await self._fetch_and_parse()
        except EnergaAuthError:
            _LOGGER.warning("Token expired. Relogging...")
            await self.async_login()
            data = await self._fetch_and_parse()
        
        meter_id = data.get("meter_id") 
        if meter_id:
            # === WARSAW TIMEZONE FIX ===
            # Wyliczamy północ dla strefy Europe/Warsaw.
            # Bez tego, HA w UTC pyta o godzinę 01:00 w nocy i gubi dane z 00:00.
            tz_warsaw = ZoneInfo("Europe/Warsaw")
            now_warsaw = datetime.now(tz_warsaw)
            today_midnight = now_warsaw.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Timestamp dla API (milisekundy)
            timestamp = int(today_midnight.timestamp() * 1000)

            _LOGGER.debug(f"Requesting chart -> Meter: {meter_id}, TS: {timestamp} (Time: {today_midnight})")

            # 1. Pobór (OBIS Import)
            try:
                cons_data = await self._fetch_chart_data(meter_id, timestamp, MO_CONSUMPTION)
                # Logujemy odpowiedź, aby upewnić się, że to IMPORT (powinno być mało kWh rano)
                _LOGGER.debug(f"IMPORT DATA (Raw): {json.dumps(cons_data)}")
                data["daily_pobor"] = self._sum_chart_values(cons_data)
            except Exception as e:
                _LOGGER.error(f"Error fetching consumption: {e}")

            # 2. Produkcja (OBIS Export)
            try:
                prod_data = await self._fetch_chart_data(meter_id, timestamp, MO_PRODUCTION)
                # Logujemy odpowiedź, aby upewnić się, że to EKSPORT (dużo kWh w dzień)
                _LOGGER.debug(f"EXPORT DATA (Raw): {json.dumps(prod_data)}")
                data["daily_produkcja"] = self._sum_chart_values(prod_data)
            except Exception as e:
                _LOGGER.error(f"Error fetching production: {e}")

        return data

    async def _fetch_chart_data(self, meter_id, timestamp, mo_type):
        """Pobiera dane wykresu."""
        params = {
            "mainChartDate": str(timestamp),
            "meterPoint": str(meter_id),
            "type": "DAY",
            "mo": mo_type
        }

        async with self._session.get(
            f"{BASE_URL}{HISTORY_ENDPOINT}",
            headers=HEADERS,
            params=params,
            ssl=False
        ) as resp:
            if resp.status in [401, 403]:
                 raise EnergaAuthError
            if resp.status != 200:
                _LOGGER.error(f"API Error {resp.status} for MO: {mo_type}")
                return None
            return await resp.json()

    def _sum_chart_values(self, json_data):
        """Sumuje wartości z wykresu."""
        total = 0.0
        try:
            if json_data and "response" in json_data and "mainChart" in json_data["response"]:
                for point in json_data["response"]["mainChart"]:
                    if "zones" in point and point["zones"]:
                        hourly_sum = sum(val for val in point["zones"] if val is not None)
                        total += hourly_sum
            else:
                 _LOGGER.warning(f"Empty/Invalid chart structure")
        except Exception as e:
             _LOGGER.error(f"Parse error: {e}")
        return round(total, 3)

    async def _fetch_and_parse(self):
        # ... (bez zmian) ...
        async with self._session.get(
            f"{BASE_URL}{DATA_ENDPOINT}", 
            headers=HEADERS, 
            ssl=False
        ) as resp:
            if resp.status in [401, 403]:
                raise EnergaAuthError
            if resp.status != 200:
                raise EnergaConnectionError(f"API Error: {resp.status}")
            
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
                "pobor": None,
                "produkcja": None,
                "ppe": meter_point.get('dev'),
                "tariff": meter_point.get('tariff'),
                "address": agreement.get('address'),
                "seller": dealer.get('name'),
                "contract_date": self._parse_date(dealer.get('start')),
                "daily_pobor": 0.0,
                "daily_produkcja": 0.0
            }
            
            for m in measurements:
                zone = m.get('zone', '')
                val = float(m.get('value', 0))
                if "A+" in zone:
                    result["pobor"] = val
                if "A-" in zone:
                    result["produkcja"] = val
                    
            return result
        except (KeyError, IndexError, TypeError) as e:
            _LOGGER.error(f"Structure error: {e}")
            return None

    def _parse_date(self, timestamp):
        if not timestamp: return "Nieznana"
        try:
            dt = datetime.fromtimestamp(int(timestamp) / 1000)
            return dt.strftime("%Y-%m-%d")
        except: return str(timestamp)