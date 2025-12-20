"""API interface for Energa Mobile v3.6.0-beta.18."""
import logging
import aiohttp
from datetime import datetime
from zoneinfo import ZoneInfo
from .const import BASE_URL, LOGIN_ENDPOINT, SESSION_ENDPOINT, DATA_ENDPOINT, CHART_ENDPOINT, HEADERS

_LOGGER = logging.getLogger(__name__)

class EnergaAuthError(Exception): pass
class EnergaConnectionError(Exception): pass
class EnergaTokenExpiredError(Exception): pass # <-- DODANY WYJĄTEK

class EnergaAPI:
    def __init__(self, username, password, session: aiohttp.ClientSession):
        self._username = username
        self._password = password
        self._session = session
        self._token = None
        self._meters_data = []

    async def async_login(self) -> bool:
        try:
            await self._api_get(SESSION_ENDPOINT)
            params = {"clientOS": "ios", "notifyService": "APNs", "username": self._username, "password": self._password}
            async with self._session.get(f"{BASE_URL}{LOGIN_ENDPOINT}", headers=HEADERS, params=params, ssl=False) as resp:
                if resp.status != 200: raise EnergaConnectionError(f"Login HTTP {resp.status}")
                try: data = await resp.json()
                except: raise EnergaConnectionError("Invalid JSON")
                if not data.get("success"): raise EnergaAuthError("Invalid credentials (API success=False)")
                
                # Token might be missing in newer API versions; session cookies are sufficient
                self._token = data.get("token") or (data.get("response") or {}).get("token")
                _LOGGER.info(f"Login successful. Token received: {bool(self._token)}")
                return True
        except aiohttp.ClientError as err: raise EnergaConnectionError from err

    async def async_get_data(self, force_refresh: bool = False) -> list[dict]:
        if force_refresh: self._meters_data = []
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
            
            _LOGGER.debug(f"Energa Meter [{m_data.get('meter_serial')}]: Total(+)={m_data.get('total_plus')}, Total(-)={m_data.get('total_minus')}, Daily(+)={m_data.get('daily_pobor')}, Daily(-)={m_data.get('daily_produkcja')}")
            updated_meters.append(m_data)
        self._meters_data = updated_meters
        return updated_meters

    async def async_get_history_hourly(self, meter_point_id, date: datetime):
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
        
        _LOGGER.debug(f"History {date.date()} (ts={ts}): Import={len(result['import'])} pts, Export={len(result['export'])} pts")
        
        return result

    async def _fetch_all_meters(self):
        data = await self._api_get(DATA_ENDPOINT)
        if not data.get("response"): raise EnergaConnectionError("Empty response in fetch_all_meters")
        
        meters_found = []
        for mp in data["response"].get("meterPoints", []):
            ag = next((a for a in data["response"].get("agreementPoints", []) if a.get("id") == mp.get("id")), {})
            if not ag and data["response"].get("agreementPoints"): ag = data["response"]["agreementPoints"][0]
            
            ppe = ag.get("code") or mp.get("ppe") or mp.get("dev") or "Unknown"
            serial = mp.get("dev") or mp.get("meterNumber") or "Unknown"
            c_date = None
            try:
                start_ts = ag.get("dealer", {}).get("start")
                if start_ts: c_date = datetime.fromtimestamp(int(start_ts) / 1000).date()
            except: pass
            
            meter_obj = {
                "meter_point_id": mp.get("id"), "ppe": ppe, "meter_serial": serial, "tariff": mp.get("tariff"), 
                "address": ag.get("address"), "contract_date": c_date, "daily_pobor": None, "daily_produkcja": None, 
                "total_plus": None, "total_minus": None, "obis_plus": None, "obis_minus": None
            }
            
            for m in mp.get("lastMeasurements", []):
                if "A+" in m.get("zone", ""): meter_obj["total_plus"] = float(m.get("value", 0))
                if "A-" in m.get("zone", ""): meter_obj["total_minus"] = float(m.get("value", 0))
            
            for obj in mp.get("meterObjects", []):
                if obj.get("obis", "").startswith("1-0:1.8.0"): meter_obj["obis_plus"] = obj.get("obis")
                elif obj.get("obis", "").startswith("1-0:2.8.0"): meter_obj["obis_minus"] = obj.get("obis")
            meters_found.append(meter_obj)
        return meters_found

    async def _fetch_chart(self, meter_id: str, obis: str, timestamp: int) -> list[float]:
        params = {"meterPoint": meter_id, "type": "DAY", "meterObject": obis, "mainChartDate": str(timestamp)}
        # Only add token if it exists, otherwise rely on cookies
        if self._token: params["token"] = self._token
        try:
            data = await self._api_get(CHART_ENDPOINT, params=params)
            return [ (p.get("zones", [0])[0] or 0.0) for p in data["response"]["mainChart"] ]
        except Exception as e:
            _LOGGER.error(f"Error fetching chart for {meter_id}: {e}")
            return []

    async def _api_get(self, path, params=None):
        url = f"{BASE_URL}{path}"
        final_params = params.copy() if params else {}
        # Only add token if parameters don't effectively have it and we have one
        if self._token and "token" not in final_params: final_params["token"] = self._token
        
        async with self._session.get(url, headers=HEADERS, params=final_params, ssl=False) as resp:
            # Handle 401/403 which might indicate session expiry or invalid token
            if resp.status == 401 or resp.status == 403:
                raise EnergaTokenExpiredError(f"API returned {resp.status} for {url}")
            
            resp.raise_for_status()
            return await resp.json()