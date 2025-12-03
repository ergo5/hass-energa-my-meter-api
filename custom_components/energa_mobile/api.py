"""API Client for Energa Mobile."""
import logging
import aiohttp
from datetime import datetime
from .const import BASE_URL, LOGIN_ENDPOINT, DATA_ENDPOINT, HEADERS

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
        """Pobranie i parsowanie danych."""
        try:
            return await self._fetch_and_parse()
        except EnergaAuthError:
            # Mechanizm ponownego logowania
            _LOGGER.warning("Token expired or unauthorized access. Attempting relogin.")
            await self.async_login()
            return await self._fetch_and_parse()
        except EnergaConnectionError as e:
            _LOGGER.error(f"Connection error during data fetch: {e}")
            raise # Przekazujemy dalej, aby koordynator ponowił próbę.

    async def _fetch_and_parse(self):
        """Wewnętrzna funkcja pobierająca."""
        try:
            async with self._session.get(
                f"{BASE_URL}{DATA_ENDPOINT}", 
                headers=HEADERS, 
                ssl=False
            ) as resp:
                # === KLUCZOWA ZMIANA: Obsługa błędów autoryzacji 401/403 ===
                if resp.status in [401, 403]:
                    # Wyrzucamy EnergaAuthError, aby wywołać async_login w async_get_data
                    raise EnergaAuthError(f"Authentication failure: {resp.status}")
                
                if resp.status != 200:
                    raise EnergaConnectionError(f"API Error: {resp.status}")
                # ==========================================================

                data = await resp.json()
                return self._parse_json(data)
        except aiohttp.ClientError as err:
            raise EnergaConnectionError from err

    def _parse_json(self, json_data):
        """Wyciągnięcie wszystkich danych (liczniki + metadane)."""
        try:
            response = json_data['response']
            meter_point = response['meterPoints'][0]
            measurements = meter_point['lastMeasurements']
            
            # Pobieramy dane z sekcji umowy
            agreement = response.get('agreementPoints', [{}])[0]
            dealer = agreement.get('dealer', {})

            result = {
                "pobor": None,
                "produkcja": None,
                "ppe": meter_point.get('dev'),
                "tariff": meter_point.get('tariff'),
                "address": agreement.get('address'),
                "seller": dealer.get('name'),
                "contract_date": self._parse_date(dealer.get('start'))
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