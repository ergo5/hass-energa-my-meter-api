"""API interface for Energa My Meter."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from .const import (
    BASE_URL,
    CHART_ENDPOINT,
    DATA_ENDPOINT,
    HEADERS,
    LOGIN_ENDPOINT,
    SESSION_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class EnergaAuthError(Exception):
    pass


class EnergaConnectionError(Exception):
    pass


class EnergaTokenExpiredError(Exception):
    pass


class EnergaAPI:
    def __init__(
        self, username, password, device_token: str, session: aiohttp.ClientSession
    ):
        self._username = username
        self._password = password
        self._device_token = device_token  # Unique per-installation token
        self._session = session
        self._token = None  # Server-returned token (may be empty in newer API)
        self._meters_data = []
        self._hass = None  # Reference to HA instance for statistics queries

    def set_hass(self, hass):
        """Set Home Assistant instance reference for database queries."""
        self._hass = hass

    async def async_login(self) -> bool:
        try:
            # Clear old cookies/session state before re-login
            self._session.cookie_jar.clear()
            self._token = None
            _LOGGER.debug("Cleared session cookies, attempting fresh login")

            await self._api_get(SESSION_ENDPOINT)
            # Use persistent device token from config (generated during installation)
            params = {
                "clientOS": "ios",
                "notifyService": "APNs",
                "username": self._username,
                "password": self._password,
                "token": self._device_token,
            }
            async with self._session.get(
                f"{BASE_URL}{LOGIN_ENDPOINT}", headers=HEADERS, params=params
            ) as resp:
                if resp.status != 200:
                    raise EnergaConnectionError(f"Login HTTP {resp.status}")
                try:
                    data = await resp.json()
                except (ValueError, TypeError, aiohttp.ContentTypeError):
                    raise EnergaConnectionError("Invalid JSON")
                if not data.get("success"):
                    raise EnergaAuthError("Invalid credentials (API success=False)")

                # Token might be missing in newer API versions; session cookies are sufficient
                self._token = data.get("token") or (data.get("response") or {}).get(
                    "token"
                )
                _LOGGER.info(
                    "Login successful. Token received: %s, Cookies: %d",
                    bool(self._token),
                    len(self._session.cookie_jar),
                )
                return True
        except aiohttp.ClientError as err:
            _LOGGER.error("Login network error: %s", err)
            raise EnergaConnectionError from err

    async def async_get_data(self, force_refresh: bool = False) -> list[dict]:
        if force_refresh:
            self._meters_data = []
        if not self._meters_data:
            self._meters_data = await self._fetch_all_meters()

        tz = ZoneInfo("Europe/Warsaw")
        ts = int(
            datetime.now(tz)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
            * 1000
        )

        updated_meters = []
        for meter in self._meters_data:
            m_data = meter.copy()
            if m_data.get("obis_plus"):
                vals = await self._fetch_chart(
                    m_data["meter_point_id"], m_data["obis_plus"], ts
                )
                m_data["daily_pobor"] = sum(vals)
            if m_data.get("obis_minus"):
                vals = await self._fetch_chart(
                    m_data["meter_point_id"], m_data["obis_minus"], ts
                )
                m_data["daily_produkcja"] = sum(vals)

            _LOGGER.debug(
                "Energa Meter [%s]: Total(+)=%s, Total(-)=%s, Daily(+)=%s, Daily(-)=%s",
                m_data.get("meter_serial"),
                m_data.get("total_plus"),
                m_data.get("total_minus"),
                m_data.get("daily_pobor"),
                m_data.get("daily_produkcja"),
            )
            updated_meters.append(m_data)
        self._meters_data = updated_meters
        return updated_meters

    async def async_get_history_hourly(self, meter_point_id, date: datetime):
        meter = next(
            (m for m in self._meters_data if m["meter_point_id"] == meter_point_id),
            None,
        )
        if not meter:
            await self.async_get_data()
            meter = next(
                (m for m in self._meters_data if m["meter_point_id"] == meter_point_id),
                None,
            )
            if not meter:
                return {"import": [], "export": []}

        tz = ZoneInfo("Europe/Warsaw")
        ts = int(
            date.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(tz)
            .timestamp()
            * 1000
        )

        result = {"import": [], "export": []}
        if meter.get("obis_plus"):
            result["import"] = await self._fetch_chart(
                meter["meter_point_id"], meter["obis_plus"], ts
            )
        if meter.get("obis_minus"):
            result["export"] = await self._fetch_chart(
                meter["meter_point_id"], meter["obis_minus"], ts
            )

        _LOGGER.debug(
            "History %s (ts=%s): Import=%d pts, Export=%d pts",
            date.date(),
            ts,
            len(result["import"]),
            len(result["export"]),
        )

        return result

    async def async_get_hourly_statistics(
        self, meter_point_id: str, start_date: datetime = None
    ):
        """Fetch hourly data from start_date to now (smart fetch).

        This method only fetches data from start_date forward, enabling
        incremental updates without re-fetching historical data.

        Args:
            meter_point_id: Meter ID to fetch data for
            start_date: Start datetime (if None, defaults to 30 days ago)

        Returns:
            dict with "import" and "export" keys containing lists of:
            {"start": datetime, "state": float (hourly value)}
        """
        from datetime import timedelta

        tz = ZoneInfo("Europe/Warsaw")
        now = datetime.now(tz)

        # Default: 30 days ago if no start_date provided
        if start_date is None:
            start_date = now - timedelta(days=30)

        # Ensure start_date is timezone-aware
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=tz)

        # Get current meter data
        meter = next(
            (m for m in self._meters_data if m["meter_point_id"] == meter_point_id),
            None,
        )
        if not meter:
            _LOGGER.warning("Meter %s not found for statistics", meter_point_id)
            return {"import": [], "export": []}

        # Calculate how many days to fetch
        days_to_fetch = (now.date() - start_date.date()).days + 1
        days_to_fetch = max(1, min(days_to_fetch, 365))  # Cap at 365 days

        _LOGGER.debug(
            "Smart fetch for %s: from %s (%d days)",
            meter_point_id,
            start_date.date(),
            days_to_fetch,
        )

        # Collect hourly data points
        all_points = {"import": [], "export": []}

        for day_offset in range(days_to_fetch):
            target_date = start_date + timedelta(days=day_offset)

            # Skip future dates
            if target_date.date() > now.date():
                break

            day_data = await self.async_get_history_hourly(meter_point_id, target_date)

            day_start = target_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).astimezone(tz)

            # Process import hours
            for hour_idx, hourly_value in enumerate(day_data.get("import", [])):
                if hourly_value and hourly_value > 0:
                    hour_dt = day_start + timedelta(hours=hour_idx + 1)
                    # Only include points after start_date
                    if hour_dt >= start_date:
                        all_points["import"].append(
                            {
                                "start": hour_dt,
                                "state": hourly_value,
                            }
                        )

            # Process export hours
            for hour_idx, hourly_value in enumerate(day_data.get("export", [])):
                if hourly_value and hourly_value > 0:
                    hour_dt = day_start + timedelta(hours=hour_idx + 1)
                    if hour_dt >= start_date:
                        all_points["export"].append(
                            {
                                "start": hour_dt,
                                "state": hourly_value,
                            }
                        )

        # Sort by time (oldest first)
        all_points["import"].sort(key=lambda x: x["start"])
        all_points["export"].sort(key=lambda x: x["start"])

        _LOGGER.info(
            "Smart fetch for %s: %d import, %d export points (from %s)",
            meter_point_id,
            len(all_points["import"]),
            len(all_points["export"]),
            start_date.date(),
        )

        return all_points

    async def _fetch_all_meters(self):
        data = await self._api_get(DATA_ENDPOINT)
        if not data.get("response"):
            raise EnergaConnectionError("Empty response in fetch_all_meters")

        meters_found = []
        for mp in data["response"].get("meterPoints", []):
            # Original v4.0.9 logic: find matching top-level agreementPoint
            ag = next(
                (
                    a
                    for a in data["response"].get("agreementPoints", [])
                    if a.get("id") == mp.get("id")
                ),
                {},
            )
            if not ag and data["response"].get("agreementPoints"):
                ag = data["response"]["agreementPoints"][0]

            # Check nested agreementPoints for PPE if not in top-level
            nested_ag = mp.get("agreementPoints", [])
            if nested_ag and nested_ag[0].get("code"):
                ppe = nested_ag[0].get("code")
            else:
                ppe = ag.get("code") or mp.get("ppe") or mp.get("dev") or "Unknown"

            serial = mp.get("dev") or mp.get("meterNumber") or "Unknown"

            # Address: from agreement, or use meter name as fallback
            address = ag.get("address")
            if not address and mp.get("name") and mp.get("name") != serial:
                address = mp.get("name")

            # Contract date from top-level agreement (dealer.start)
            c_date = None
            try:
                start_ts = ag.get("dealer", {}).get("start")
                if start_ts:
                    c_date = datetime.fromtimestamp(int(start_ts) / 1000).date()
            except (ValueError, TypeError, OSError):
                pass

            meter_obj = {
                "meter_point_id": mp.get("id"),
                "ppe": ppe,
                "meter_serial": serial,
                "tariff": mp.get("tariff"),
                "address": address,
                "contract_date": c_date,
                "daily_pobor": None,
                "daily_produkcja": None,
                "total_plus": None,
                "total_minus": None,
                "obis_plus": None,
                "obis_minus": None,
            }

            for m in mp.get("lastMeasurements", []):
                if "A+" in m.get("zone", ""):
                    meter_obj["total_plus"] = float(m.get("value", 0))
                if "A-" in m.get("zone", ""):
                    meter_obj["total_minus"] = float(m.get("value", 0))

            for obj in mp.get("meterObjects", []):
                if obj.get("obis", "").startswith("1-0:1.8.0"):
                    meter_obj["obis_plus"] = obj.get("obis")
                elif obj.get("obis", "").startswith("1-0:2.8.0"):
                    meter_obj["obis_minus"] = obj.get("obis")
            meters_found.append(meter_obj)
        return meters_found

    async def _fetch_chart(
        self, meter_id: str, obis: str, timestamp: int
    ) -> list[float]:
        params = {
            "meterPoint": meter_id,
            "type": "DAY",
            "meterObject": obis,
            "mainChartDate": str(timestamp),
        }
        # Only add token if it exists, otherwise rely on cookies
        if self._token:
            params["token"] = self._token
        try:
            data = await self._api_get(CHART_ENDPOINT, params=params)
            return [
                (p.get("zones", [0])[0] or 0.0) for p in data["response"]["mainChart"]
            ]
        except EnergaTokenExpiredError:
            raise  # Propagate to coordinator for re-login
        except Exception as e:
            _LOGGER.error("Error fetching chart for %s: %s", meter_id, e)
            return []

    async def _api_get(self, path, params=None):
        url = f"{BASE_URL}{path}"
        final_params = params.copy() if params else {}
        # Only add token if parameters don't effectively have it and we have one
        if self._token and "token" not in final_params:
            final_params["token"] = self._token

        async with self._session.get(url, headers=HEADERS, params=final_params) as resp:
            # Handle 401/403 which might indicate session expiry or invalid token
            if resp.status == 401 or resp.status == 403:
                raise EnergaTokenExpiredError(f"API returned {resp.status} for {url}")

            resp.raise_for_status()
            return await resp.json()
