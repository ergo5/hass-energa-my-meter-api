import aiohttp
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import BASE, UA

class EnergaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, cfg):
        super().__init__(
            hass,
            logger=hass.logger,
            name="EnergaCoordinator",
            update_interval=timedelta(minutes=15),
        )
        self.hass = hass
        self.username = cfg["username"]
        self.password = cfg["password"]
        self.token = cfg["token"]
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))

    async def _api(self, path, params=None):
        url = BASE + path
        async with self.session.get(url, headers=UA, params=params) as r:
            r.raise_for_status()
            return await r.json()

    async def _login(self):
        await self._api("/apihelper/SessionStatus")
        await self._api("/apihelper/UserLogin", {
            "username": self.username,
            "password": self.password,
            "token": self.token,
            "clientOS": "ios",
            "notifyService": "APNs"
        })

    async def _get_user(self):
        d = await self._api("/resources/user/data")
        return d["response"]

    async def _chart_day(self, mp, obis, date):
        return await self._api("/resources/mchart", {
            "meterPoint": mp,
            "type": "DAY",
            "meterObject": obis,
            "mainChartDate": int(date.timestamp() * 1000)
        })

    async def _async_update_data(self):
        await self._login()
        user = await self._get_user()

        mp = user["meterPoints"][0]["id"]

        # TOTAL A+ / A-
        last = user["meterPoints"][0]["lastMeasurements"]
        total_aplus = last[0]["value"]
        total_aminus = last[1]["value"]

        # Godzinówki DAY
        date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        day_plus = await self._chart_day(mp, "1-0:1.8.0*255", date)
        day_minus = await self._chart_day(mp, "1-0:2.8.0*255", date)

        h_aplus = [z[0] for z in (p["zones"] for p in day_plus["response"]["mainChart"])]
        h_aminus = [z[0] for z in (p["zones"] for p in day_minus["response"]["mainChart"])]

        return {
            "total_aplus": total_aplus,
            "total_aminus": total_aminus,
            "hourly_aplus": h_aplus,
            "hourly_aminus": h_aminus,
        }
