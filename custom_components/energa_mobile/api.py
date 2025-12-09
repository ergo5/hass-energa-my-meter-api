"""API Client for Energa Mobile."""
import logging
import aiohttp
from datetime import datetime, timedelta, timezone
from .const import BASE_URL, LOGIN_ENDPOINT, DATA_ENDPOINT, HEADERS, HISTORY_ENDPOINT, OBIS_CONSUMPTION, OBIS_PRODUCTION

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
        """Pobranie danych głównych i pomiarów godzinowych."""
        
        # 1. Pobranie danych głównych (User Data)
        try:
            data = await self._fetch_and_parse()
        except EnergaAuthError:
            _LOGGER.warning("Token expired. Relogging...")
            await self.async_login()
            data = await self._fetch_and_parse()
        
        # 2. Pobranie szczegółowych danych dziennych (Wykresy)
        # Potrzebujemy ID licznika z danych głównych
        meter_id = data.get("meter_id") 
        if meter_id:
             # Pobieramy dla dzisiejszego dnia (od północy)
            now = datetime.now()
            today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            timestamp = int(today_midnight.timestamp() * 1000)

            # Pobór (Consumption)
            try:
                cons_data = await self._fetch_chart_data(meter_id, timestamp, OBIS_CONSUMPTION)
                data["daily_pobor"] = self._sum_chart_values(cons_data)
            except Exception as e:
                _LOGGER.error(f"Error fetching consumption chart: {e}")

            # Produkcja (Production)
            try:
                prod_data = await self._fetch_chart_data(meter_id, timestamp, OBIS_PRODUCTION)
                data["daily_produkcja"] = self._sum_chart_values(prod_data)
            except Exception as e:
                _LOGGER.error(f"Error fetching production chart: {e}")

        return data

    async def _fetch_chart_data(self, meter_id, timestamp, obis_code):
        """Pobiera dane wykresu dla konkretnego OBIS code."""
        # Parametry zgodne z analizą ruchu sieciowego
        params = {
            "mainChartDate": str(timestamp),
            "meterPoint": str(meter_id),
            "type": "DAY",
            "mo": obis_code # Meter Object determines consumption vs production
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
                raise EnergaConnectionError(f"Chart API Error: {resp.status}")
            
            return await resp.json()

    def _sum_chart_values(self, json_data):
        """Sumuje wartości z wykresu (mainChart)."""
        total = 0.0
        try:
            if json_data and "response" in json_data and "mainChart" in json_data["response"]:
                for point in json_data["response"]["mainChart"]:
                    # mainChart zawiera listę punktów. Interesuje nas suma wartości z 'zones'
                    # zones to zazwyczaj lista [strefa1, strefa2, strefa3]
                    if "zones" in point and point["zones"]:
                        # Sumujemy wartości ze wszystkich stref dla danej godziny
                        hourly_sum = sum(val for val in point["zones"] if val is not None)
                        total += hourly_sum
        except Exception as e:
             _LOGGER.error(f"Error parsing chart data: {e}")
        return round(total, 3)

    async def _fetch_and_parse(self):
        """Wewnętrzna funkcja pobierająca dane główne."""
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
        """Wyciągnięcie danych głównych."""
        try:
            response = json_data['response']
            meter_point = response['meterPoints'][0]
            measurements = meter_point['lastMeasurements']
            
            agreement = response.get('agreementPoints', [{}])[0]
            dealer = agreement.get('dealer', {})

            result = {
                "meter_id": meter_point.get('id'), # Potrzebne do zapytań o wykresy
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
            _LOGGER.error(f"Błąd struktury danych Energa: {e}")
            return None

    def _parse_date(self, timestamp):
        if not timestamp: return "Nieznana"
        try:
            dt = datetime.fromtimestamp(int(timestamp) / 1000)
            return dt.strftime("%Y-%m-%d")
        except: return str(timestamp)