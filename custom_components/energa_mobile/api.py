"""API interface for Energa My Meter."""

import asyncio
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
        self,
        username,
        password,
        device_token: str,
        session: aiohttp.ClientSession,
        create_session_fn=None,
    ):
        self._username = username
        self._password = password
        self._device_token = device_token  # Unique per-installation token
        self._session = session
        self._create_session_fn = create_session_fn or (lambda: aiohttp.ClientSession())
        self._token = None  # Server-returned token (may be empty in newer API)
        self._meters_data = []
        self._hass = None  # Reference to HA instance for statistics queries

    def set_hass(self, hass):
        """Set Home Assistant instance reference for database queries."""
        self._hass = hass

    def has_multi_zone_meters(self) -> bool:
        """Check if any meter uses a multi-zone tariff (e.g. G12w)."""
        return any(m.get("zone_count", 1) > 1 for m in self._meters_data)

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
                # Fetch total daily consumption (sum of all zones)
                vals = await self._fetch_chart(
                    m_data["meter_point_id"], m_data["obis_plus"], ts
                )
                m_data["daily_pobor"] = sum(vals)

                # Fetch per-zone daily consumption for G12w
                if m_data.get("zone_count", 1) > 1:
                    vals_1 = await self._fetch_chart(
                        m_data["meter_point_id"], m_data["obis_plus"], ts, zone_index=0
                    )
                    vals_2 = await self._fetch_chart(
                        m_data["meter_point_id"], m_data["obis_plus"], ts, zone_index=1
                    )
                    m_data["daily_pobor_1"] = sum(vals_1)
                    m_data["daily_pobor_2"] = sum(vals_2)

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
            # Total import (sum of all zones)
            result["import"] = await self._fetch_chart(
                meter["meter_point_id"], meter["obis_plus"], ts
            )
            # Per-zone import for G12w
            if meter.get("zone_count", 1) > 1:
                result["import_1"] = await self._fetch_chart(
                    meter["meter_point_id"], meter["obis_plus"], ts, zone_index=0
                )
                result["import_2"] = await self._fetch_chart(
                    meter["meter_point_id"], meter["obis_plus"], ts, zone_index=1
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

        Returns:
            dict with keys like "import", "import_1", "import_2", "export"
            containing lists of: {"start": datetime, "state": float}
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

        has_zones = meter.get("zone_count", 1) > 1

        # Calculate how many days to fetch
        days_to_fetch = (now.date() - start_date.date()).days + 1
        days_to_fetch = max(1, min(days_to_fetch, 365))  # Cap at 365 days

        _LOGGER.debug(
            "Smart fetch for %s: from %s (%d days, zones=%s)",
            meter_point_id,
            start_date.date(),
            days_to_fetch,
            has_zones,
        )

        # Collect hourly data points
        keys = ["import", "export"]
        if has_zones:
            keys.extend(["import_1", "import_2"])
        all_points = {k: [] for k in keys}

        for day_offset in range(days_to_fetch):
            target_date = start_date + timedelta(days=day_offset)

            # Skip future dates
            if target_date.date() > now.date():
                break

            if day_offset > 0:
                await asyncio.sleep(0.3)

            day_data = await self.async_get_history_hourly(meter_point_id, target_date)

            day_start = target_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).astimezone(tz)

            # Process each data key
            for key in keys:
                for hour_idx, hourly_value in enumerate(day_data.get(key, [])):
                    if hourly_value is not None and hourly_value >= 0:
                        hour_dt = day_start + timedelta(hours=hour_idx)
                        # Only include points after start_date
                        if hour_dt >= start_date:
                            all_points[key].append(
                                {
                                    "start": hour_dt,
                                    "state": hourly_value,
                                }
                            )

        # Sort by time (oldest first)
        for key in keys:
            all_points[key].sort(key=lambda x: x["start"])

        _LOGGER.info(
            "Smart fetch for %s: %d import, %d export points (from %s)%s",
            meter_point_id,
            len(all_points["import"]),
            len(all_points["export"]),
            start_date.date(),
            f", zone1={len(all_points.get('import_1', []))}, zone2={len(all_points.get('import_2', []))}"
            if has_zones
            else "",
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
                "total_plus_1": None,
                "total_plus_2": None,
                "total_minus_1": None,
                "total_minus_2": None,
                "obis_plus": None,
                "obis_minus": None,
                "zone_count": 1,
            }

            # Sum all A+ and A- zones; detect multi-zone tariffs (G12w)
            total_plus_sum = 0.0
            total_minus_sum = 0.0
            zone_numbers_seen = set()
            for m in mp.get("lastMeasurements", []):
                zone_name = m.get("zone", "")
                value = float(m.get("value", 0))
                if "A+" in zone_name:
                    total_plus_sum += value
                    if "strefa 1" in zone_name:
                        meter_obj["total_plus_1"] = value
                        zone_numbers_seen.add(1)
                    elif "strefa 2" in zone_name:
                        meter_obj["total_plus_2"] = value
                        zone_numbers_seen.add(2)
                if "A-" in zone_name:
                    total_minus_sum += value
                    if "strefa 1" in zone_name:
                        meter_obj["total_minus_1"] = value
                    elif "strefa 2" in zone_name:
                        meter_obj["total_minus_2"] = value

            if total_plus_sum > 0:
                meter_obj["total_plus"] = total_plus_sum
            if total_minus_sum > 0:
                meter_obj["total_minus"] = total_minus_sum

            # Detect zone count from lastMeasurements
            if len(zone_numbers_seen) > 1:
                meter_obj["zone_count"] = len(zone_numbers_seen)
                _LOGGER.info(
                    "Meter %s: multi-zone tariff detected (%s), %d zones",
                    serial,
                    mp.get("tariff"),
                    meter_obj["zone_count"],
                )

            for obj in mp.get("meterObjects", []):
                if obj.get("obis", "").startswith("1-0:1.8.0"):
                    meter_obj["obis_plus"] = obj.get("obis")
                elif obj.get("obis", "").startswith("1-0:2.8.0"):
                    meter_obj["obis_minus"] = obj.get("obis")
            meters_found.append(meter_obj)
        return meters_found

    async def _fetch_chart(
        self, meter_id: str, obis: str, timestamp: int, zone_index: int | None = None
    ) -> list[float]:
        """Fetch chart data for a meter.

        Args:
            meter_id: Meter point ID
            obis: OBIS code (e.g. 1-0:1.8.0*255)
            timestamp: Day timestamp in milliseconds
            zone_index: None=sum all zones, 0=zone 1, 1=zone 2
        """
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
            results = []
            for p in data["response"]["mainChart"]:
                zones = p.get("zones", [])
                if zone_index is not None:
                    # Specific zone
                    val = zones[zone_index] if zone_index < len(zones) else None
                    results.append(val or 0.0)
                else:
                    # Sum all zones (total)
                    total = sum(z or 0.0 for z in zones)
                    results.append(total)
            return results
        except EnergaTokenExpiredError:
            raise  # Propagate to coordinator for re-login
        except Exception as e:
            _LOGGER.error("Error fetching chart for %s: %s", meter_id, e)
            return []

    async def _api_get(self, path, params=None):
        for attempt in range(2):
            # Recover from closed session
            if self._session.closed:
                _LOGGER.warning(
                    "Session closed (attempt %d), creating new session and re-logging in",
                    attempt + 1,
                )
                self._session = self._create_session_fn()
                await self.async_login()

            url = f"{BASE_URL}{path}"
            final_params = params.copy() if params else {}
            if self._token and "token" not in final_params:
                final_params["token"] = self._token

            try:
                async with self._session.get(
                    url, headers=HEADERS, params=final_params
                ) as resp:
                    if resp.status in (401, 403):
                        if attempt == 0:
                            _LOGGER.warning(
                                "Token expired (HTTP %d), re-logging in", resp.status
                            )
                            await self.async_login()
                            continue
                        raise EnergaTokenExpiredError(
                            f"API returned {resp.status} for {url}"
                        )
                    resp.raise_for_status()
                    return await resp.json()
            except (aiohttp.ClientError, RuntimeError) as err:
                if attempt == 0 and (
                    self._session.closed or "Session is closed" in str(err)
                ):
                    _LOGGER.warning("Request failed (session issue: %s), retrying", err)
                    continue
                raise EnergaConnectionError(str(err)) from err
        # Should not reach here, but safety net
        raise EnergaConnectionError("Max retries exceeded in _api_get")
