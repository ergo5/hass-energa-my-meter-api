"""API Client for Energa Mobile v2.7.8."""
import logging
import aiohttp
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
        self._meter_data = None

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
        """Pobiera dane bieżące (sumy dzienne)."""
        if not self._meter_data: self._meter_data = await self._fetch_user_metadata()
        tz = ZoneInfo("Europe/Warsaw")
        ts = int(datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        data = self._meter_data.copy()
        
        if data.get("obis_plus"):
            vals = await self._fetch_chart(data["meter_point_id"], data["obis_plus"], ts)
            data["daily_pobor"] = sum(vals)
        if data.get("obis_minus"):
            vals = await self._fetch_chart(data["meter_point_id"], data["obis_minus"], ts)
            data["daily_produkcja"] = sum(vals)
        return data

    async def async_get_history_hourly(self, date: datetime):
        """Pobiera pełne wektory godzinowe dla historycznego dnia."""
        if not self._meter_data: self._meter_data = await self._fetch_user_metadata()
        ts = int(date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        result = {"import": [], "export": []}
        
        if self._meter_data.get("obis_plus"):
            result["import"] = await self._fetch_chart(self._meter_data["meter_point_id"], self._meter_data["obis_plus"], ts)
        if self._meter_data.get("obis_minus"):
            result["export"] = await self._fetch_chart(self._meter_data["meter_point_id"], self._meter_data["obis_minus"], ts)
        return result

    async def _fetch_user_metadata(self):
        data = await self._api_get(DATA_ENDPOINT)
        if not data.get("response"): raise EnergaConnectionError("Empty response")
        mp = data["response"]["meterPoints"][0]
        ag = data["response"].get("agreementPoints", [{}])[0]
        
        c_date = None
        try:
            start_ts = ag.get("dealer", {}).get("start")
            if start_ts: c_date = datetime.fromtimestamp(int(start_ts) / 1000).date()
        except: pass

        res = {
            "meter_point_id": mp.get("id"), "ppe": mp.get("dev"), "tariff": mp.get("tariff"), 
            "address": ag.get("address"), "contract_date": c_date,
            "daily_pobor": 0.0, "daily_produkcja": 0.0, "total_plus": 0.0, "total_minus": 0.0, 
            "obis_plus": None, "obis_minus": None
        }
        for m in mp.get("lastMeasurements", []):
            if "A+" in m.get("zone", ""): res["total_plus"] = float(m.get("value", 0))
            if "A-" in m.get("zone", ""): res["total_minus"] = float(m.get("value", 0))
        for obj in mp.get("meterObjects", []):
            if obj.get("obis", "").startswith("1-0:1.8.0"): res["obis_plus"] = obj.get("obis")
            elif obj.get("obis", "").startswith("1-0:2.8.0"): res["obis_minus"] = obj.get("obis")
        return res

    async def _fetch_chart(self, meter_id, obis, timestamp):
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
            if resp.status == 401: raise EnergaAuthError
            resp.raise_for_status()
            return await resp.json()