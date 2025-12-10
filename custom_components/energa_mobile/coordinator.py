from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import BASE, UA, DOMAIN

class EnergaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, creds):
        super().__init__(
            hass,
            logger=hass.logger,
            name=DOMAIN,
            update_interval=timedelta(minutes=30),
        )
        self.username = creds["username"]
        self.password = creds["password"]

        self.meter_id = None
        self.meterpoint = None

    async def _login(self, session):
        params = {
            "clientOS": "ios",
            "notifyService": "APNs",
            "token": "abcdef0123456789abcdef0123456789",
            "username": self.username,
            "password": self.password,
        }
        await session.get(f"{BASE}/apihelper/SessionStatus", headers=UA, ssl=False)
        await session.get(f"{BASE}/apihelper/UserLogin", headers=UA, params=params, ssl=False)

    async def _fetch_user(self, session):
        r = await session.get(f"{BASE}/resources/user/data", headers=UA, ssl=False)
        js = await r.json()
        u = js["response"]

        mp = u["meterPoints"][0]
        self.meter_id = mp["name"]
        self.meterpoint = mp["id"]

        return u

    async def _fetch_totals(self, session):
        """
        Pobieramy TOTAL A+ i A-
        """
        r = await session.get(f"{BASE}/resources/user/data", headers=UA, ssl=False)
        js = await r.json()
        meas = js["response"]["lastMeasurements"]

        aplus = meas[0]["value"]
        aminus = meas[1]["value"]

        return {"aplus": aplus, "aminus": aminus}

    async def _fetch_hourly(self, session):
        """
        Pobór i produkcja godzinowa — dzień bieżący (24 punkty)
        """
        now = datetime.now(timezone.utc).astimezone()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        ts = int(midnight.timestamp() * 1000)

        params_plus = {
            "meterPoint": self.meterpoint,
            "meterObject": "1-0:1.8.0*255",
            "type": "DAY",
            "mainChartDate": ts,
        }

        params_minus = {
            "meterPoint": self.meterpoint,
            "meterObject": "1-0:2.8.0*255",
            "type": "DAY",
            "mainChartDate": ts,
        }

        r1 = await session.get(f"{BASE}/resources/mchart", headers=UA, params=params_plus, ssl=False)
        r2 = await session.get(f"{BASE}/resources/mchart", headers=UA, params=params_minus, ssl=False)

        js1 = await r1.json()
        js2 = await r2.json()

        arr_plus = [x["zones"][0] for x in js1["response"]["mainChart"]]
        arr_minus = [x["zones"][0] for x in js2["response"]["mainChart"]]

        return {"h_aplus": sum(arr_plus), "h_aminus": sum(arr_minus)}

    async def _async_update_data(self):
        async with aiohttp.ClientSession() as session:
            await self._login(session)

            await self._fetch_user(session)
            totals = await self._fetch_totals(session)
            hourly = await self._fetch_hourly(session)

            return {"total": totals, "hourly": hourly}
