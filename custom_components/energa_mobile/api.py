"""API Client for Energa Mobile v3.5.5."""
import logging
import aiohttp
from datetime import datetime
from zoneinfo import ZoneInfo
from .const import BASE_URL, LOGIN_ENDPOINT, SESSION_ENDPOINT, DATA_ENDPOINT, CHART_ENDPOINT, HEADERS

_LOGGER = logging.getLogger(__name__)

class EnergaAuthError(Exception): pass
class EnergaConnectionError(Exception): pass
class EnergaTokenExpiredError(Exception): pass # <--- NOWY WYJĄTEK

class EnergaAPI:
    def __init__(self, username, password, session: aiohttp.ClientSession):
        self._username = username
        self._password = password
        self._session = session
        self._token = None
        self._meters_data = []

    async def async_login(self):
        try:
            await self._api_get(SESSION_ENDPOINT)
            params = {"clientOS": "ios", "notifyService": "APNs", "username": self._username, "password": self._password}
            async with self._session.get(f"{BASE_URL}{LOGIN_ENDPOINT}", headers=HEADERS, params=params, ssl=False) as resp:
                if resp.status != 200: raise EnergaConnectionError(f"Login HTTP {resp.status}")
                try: data = await resp.json()
                except: raise EnergaConnectionError("Invalid JSON")
                if not data.get("success"): raise EnergaAuthError("Invalid credentials")
                self._token = data.get("token") or (data.get("response") or {}).get("token")
                return True
        except aiohttp.ClientError as err: raise EnergaConnectionError from err

    async def async_get_data(self):
        # ... reszta funkcji async_get_data pozostaje bez zmian ...
        if not self._meters_data: self._meters_data = await self._fetch_all_meters()
        tz = ZoneInfo("Europe/Warsaw")
        ts = int(datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        
        updated_meters = []
        for meter in self._meters_data:
            m_data = meter.copy()
            if m_data.get("obis_plus"):
                vals = await self._fetch_chart(m_data["meter_point_id"], m_data["obis_plus"], ts)
                m_data["daily_pobor"] = sum(vals)
            if m_data.get("obis_minus"):
                vals = await self._fetch_chart(m_data["meter_point_id"], m_data["obis_minus"], ts)
                m_data["daily_produkcja"] = sum(vals)
            updated_meters.append(m_data)
        self._meters_data = updated_meters
        return updated_meters

    async def async_get_history_hourly(self, meter_point_id, date: datetime):
        # ... reszta funkcji async_get_history_hourly pozostaje bez zmian ...
        meter = next((m for m in self._meters_data if m["meter_point_id"] == meter_point_id), None)
        if not meter:
            await self.async_get_data()
            meter = next((m for m in self._meters_data if m["meter_point_id"] == meter_point_id), None)
            if not meter: return {"import": [], "export": []}
        
        tz = ZoneInfo("Europe/Warsaw")
        ts = int(date.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz).timestamp() * 1000)

        result = {"import": [], "export": []}
        if meter.get("obis_plus"):
            result["import"] = await self._fetch_chart(meter["meter_point_id"], meter["obis_plus"], ts)
        if meter.get("obis_minus"):
            result["export"] = await self._fetch_chart(meter["meter_point_id"], meter["obis_minus"], ts)
        
        _LOGGER.debug(f"Historia {date.date()} (ts={ts}): Import={len(result['import'])} pkt, Export={len(result['export'])} pkt")
        
        return result


    async def _fetch_chart(self, meter_id, obis, timestamp):
        # ... reszta funkcji _fetch_chart pozostaje bez zmian ...
        params = {"meterPoint": meter_id, "type": "DAY", "meterObject": obis, "mainChartDate": str(timestamp)}
        if self._token: params["token"] = self._token
        data = await self._api_get(CHART_ENDPOINT, params=params)
        try: return [ (p.get("zones", [0])[0] or 0.0) for p in data["response"]["mainChart"] ]
        except: return []

    async def _api_get(self, path, params=None):
        url = f"{BASE_URL}{path}"
        final_params = params.copy() if params else {}
        if self._token and "token" not in final_params: final_params["token"] = self._token
        async with self._session.get(url, headers=HEADERS, params=final_params, ssl=False) as resp:
            # FIX: OBSŁUGA BŁĘDÓW 401/403
            if resp.status == 401 or resp.status == 403:
                # Wyrzucamy nasz nowy wyjątek. Coordinator go złapie i spróbuje ponownego logowania.
                raise EnergaTokenExpiredError(f"API returned {resp.status} for {url}")
            
            resp.raise_for_status()
            return await resp.json()