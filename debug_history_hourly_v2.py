import aiohttp
import asyncio
import json
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# === DANE ===
USERNAME = "user"
PASSWORD = "password"
# ============

BASE_URL = "https://api-mojlicznik.energa-operator.pl/dp"
HEADERS = {
    "User-Agent": "Energa/3.0.3 (pl.energa-operator.mojlicznik; build:1; iOS 26.2.0) Alamofire/3.0.3",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

async def main():
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        print("--- 1. LOGOWANIE ---")
        await session.get(f"{BASE_URL}/apihelper/SessionStatus", headers=HEADERS, ssl=False)
        
        login_params = {"clientOS": "ios", "notifyService": "APNs", "username": USERNAME, "password": PASSWORD}
        async with session.get(f"{BASE_URL}/apihelper/UserLogin", params=login_params, headers=HEADERS, ssl=False) as resp:
            data = await resp.json()
            if not data.get("success"):
                print("❌ Błąd logowania")
                return
            token = data.get("token") or (data.get("response") or {}).get("token")
            print("✅ Zalogowano.")

        print("\n--- 2. NAMIERZANIE DATY UMOWY ---")
        contract_date = None
        data_params = {"token": token} if token else {}
        
        async with session.get(f"{BASE_URL}/resources/user/data", params=data_params, headers=HEADERS, ssl=False) as resp:
            user_data = await resp.json()
            resp_data = user_data["response"]
            mp = resp_data['meterPoints'][0]
            meter_id = str(mp.get('id'))
            
            # Szukanie daty w 'dealer -> start' (tam gdzie ją widzieliśmy w logach)
            try:
                ag = resp_data.get("agreementPoints", [{}])[0]
                dealer = ag.get("dealer", {})
                start_ts_raw = dealer.get("start")
                
                print(f"   Raw Timestamp z API: {start_ts_raw}")
                
                if start_ts_raw:
                    # Konwersja ms -> data
                    contract_date = datetime.fromtimestamp(int(start_ts_raw) / 1000).date()
                    print(f"   ✅ PRZELICZONA DATA UMOWY: {contract_date}")
                else:
                    print("   ❌ Nie znaleziono timestampu w agreementPoints -> dealer -> start")
            except Exception as e:
                print(f"   ❌ Błąd parsowania daty: {e}")

            # OBIS
            obis_imp = next((o['obis'] for o in mp.get("meterObjects", []) if o['obis'].startswith("1-0:1.8.0")), None)
            obis_exp = next((o['obis'] for o in mp.get("meterObjects", []) if o['obis'].startswith("1-0:2.8.0")), None)

        print("\n--- 3. POBIERANIE HISTORII OD DNIA UMOWY ---")
        if not contract_date:
            print("Brak daty, testuję dla wczoraj.")
            contract_date = datetime.now().date() - timedelta(days=1)

        # Testujemy 3 dni od startu umowy
        tz = ZoneInfo("Europe/Warsaw")
        
        for i in range(3):
            target_day = contract_date + timedelta(days=i)
            ts_ms = int(datetime(target_day.year, target_day.month, target_day.day, tzinfo=tz).timestamp() * 1000)
            
            print(f"\n📅 Dzień: {target_day} (TS: {ts_ms})")
            
            # POBÓR
            if obis_imp:
                vec = await fetch_vector(session, meter_id, obis_imp, ts_ms, token)
                print(f"   Import (h): {vec}")
                print(f"   SUMA: {sum(vec):.3f} kWh")
            
            # PRODUKCJA
            if obis_exp:
                vec = await fetch_vector(session, meter_id, obis_exp, ts_ms, token)
                print(f"   Export (h): {vec}")
                print(f"   SUMA: {sum(vec):.3f} kWh")

async def fetch_vector(session, meter_id, obis, ts, token):
    params = {"meterPoint": meter_id, "type": "DAY", "meterObject": obis, "mainChartDate": str(ts)}
    if token: params["token"] = token
    async with session.get(f"{BASE_URL}/resources/mchart", params=params, headers=HEADERS, ssl=False) as resp:
        try:
            d = await resp.json()
            return [ (p.get("zones", [0])[0] or 0.0) for p in d["response"]["mainChart"] ]
        except: return []

if __name__ == "__main__":
    asyncio.run(main())