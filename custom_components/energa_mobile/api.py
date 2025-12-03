"""API Client for Energa Mobile."""
import logging
import aiohttp
from datetime import datetime, timedelta, timezone 
from .const import BASE_URL, LOGIN_ENDPOINT, DATA_ENDPOINT, HEADERS, HISTORY_ENDPOINT

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
        
        # Próba pobrania danych głównych
        try:
            data = await self._fetch_and_parse()
        except EnergaAuthError:
            _LOGGER.warning("Token expired or unauthorized access during main fetch. Attempting relogin.")
            await self.async_login()
            data = await self._fetch_and_parse()
        except EnergaConnectionError as e:
            _LOGGER.error(f"Connection error during main data fetch: {e}")
            raise # Przekazujemy dalej, aby koordynator ponowił próbę.
            
        # Pobieramy dane z ostatniego pełnego dnia i dzisiejszego dnia do teraz
        now_utc = datetime.now(timezone.utc)
        yesterday = now_utc.date() - timedelta(days=1)

        start_date = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc).isoformat()
        end_date = now_utc.isoformat()
        
        # Pobieranie pomiarów godzinowych
        try:
            measurements = await self._fetch_measurements(start_date, end_date)
            # Agregujemy dane historyczne do głównego słownika
            data.update(self._process_measurements(measurements))
        except EnergaAuthError:
            _LOGGER.warning("Token expired during measurements fetch. Attempting relogin.")
            await self.async_login()
            measurements = await self._fetch_measurements(start_date, end_date)
            data.update(self._process_measurements(measurements))
        except EnergaConnectionError as e:
            _LOGGER.error(f"Connection error during measurements fetch: {e}")
            pass # Ignorujemy, aby nie zepsuć odczytu głównego, jeśli pomiary godzinowe zawiodą.

        return data
    
    async def _fetch_measurements(self, start_date: str, end_date: str):
        """Pobiera dane zużycia godzinowego dla podanego zakresu."""
        params = {
            "dateFrom": f"{start_date}Z",
            "dateTo": f"{end_date}Z",
        }
        
        try:
            async with self._session.get(
                f"{BASE_URL}{HISTORY_ENDPOINT}", 
                headers=HEADERS, 
                params=params,
                ssl=False
            ) as resp:
                if resp.status in [401, 403]:
                    raise EnergaAuthError(f"Measurements Auth failure: {resp.status}")
                if resp.status != 200:
                    _LOGGER.error(f"Failed to fetch measurements: API Status {resp.status}")
                    return None

                data = await resp.json()
                return data

        except aiohttp.ClientError as err:
            raise EnergaConnectionError from err

    async def _fetch_and_parse(self):
        """Wewnętrzna funkcja pobierająca dane główne."""
        try:
            async with self._session.get(
                f"{BASE_URL}{DATA_ENDPOINT}", 
                headers=HEADERS, 
                ssl=False
            ) as resp:
                # Wymuszenie błędu auth dla 401/403
                if resp.status in [401, 403]:
                    raise EnergaAuthError(f"Authentication failure: {resp.status}")
                if resp.status != 200:
                    raise EnergaConnectionError(f"API Error: {resp.status}")
                
                data = await resp.json()
                return self._parse_json(data)
        except aiohttp.ClientError as err:
            raise EnergaConnectionError from err

    def _process_measurements(self, measurements_data):
        """Przetwarza surowe dane godzinowe i wylicza dzienne zużycie/produkcję."""
        if not measurements_data or 'response' not in measurements_data:
            return {"daily_pobor": 0, "daily_produkcja": 0}

        total_pobor = 0
        total_produkcja = 0
        today = datetime.now(timezone.utc).date()
        
        try:
            for point in measurements_data['response']['meterPoints']:
                for m in point['measurements']:
                    measurement_time = datetime.fromisoformat(m['time']).astimezone(timezone.utc)
                    
                    # Interesują nas tylko pomiary z dnia dzisiejszego (do teraz)
                    if measurement_time.date() == today:
                        if m['zone'] == 'A+':
                            total_pobor += m['value']
                        elif m['zone'] == 'A-':
                            total_produkcja += m['value']
                            
            return {
                "daily_pobor": round(total_pobor, 3), 
                "daily_produkcja": round(total_produkcja, 3)
            }
            
        except (KeyError, IndexError, TypeError) as e:
            _LOGGER.error(f"Błąd parsowania danych pomiarowych: {e}")
            return {"daily_pobor": 0, "daily_produkcja": 0}

    def _parse_json(self, json_data):
        """Wyciągnięcie danych głównych."""
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