import aiohttp
import asyncio
import json
from datetime import datetime, timedelta

# === KONFIGURACJA ===
USERNAME = "user"
PASSWORD = "password"
BASE_URL = "https://api-mojlicznik.energa-operator.pl/dp"
HEADERS = {"User-Agent": "Energa/3.0.3", "Content-Type": "application/json"}

# ILE DNI TESTOWAĆ (Wystarczy 5, żeby potwierdzić, że nas nie banują)
TEST_DAYS_COUNT = 5 
# ====================

async def main():
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        print("--- TEST HAMULCA BEZPIECZEŃSTWA (Rate Limiting) ---")
        
        # 1. Login
        print("1. Logowanie...")
        await session.get(f"{BASE_URL}/apihelper/SessionStatus", headers=HEADERS, ssl=False)
        params = {"clientOS": "ios", "notifyService": "APNs", "username": USERNAME, "password": PASSWORD}
        
        token = None
        async with session.get(f"{BASE_URL}/apihelper/UserLogin", params=params, headers=HEADERS, ssl=False) as resp:
            data = await resp.json()
            if data.get("success"):
                token = data.get("token") or (data.get("response") or {}).get("token")
                print("   ✅ Zalogowano.")
            else:
                print(f"   ❌ Błąd logowania: {data}")
                return

        # 2. Pobranie Metadanych (Data Umowy)
        print("\n2. Pobieranie danych licznika...")
        p_data = {"token": token} if token else {}
        async with session.get(f"{BASE_URL}/resources/user/data", params=p_data, headers=HEADERS, ssl=False) as resp:
            ud = await resp.json()
            mp = ud["response"]["meterPoints"][0]
            meter_id = str(mp["id"])
            
            # Data Umowy
            ag = ud["response"].get("agreementPoints", [{}])[0]
            ts = ag.get("dealer", {}).get("start")
            
            if ts:
                start_date = datetime.fromtimestamp(int(ts)/1000).date()
                print(f"   ✅ Data Umowy: {start_date}")
            else:
                start_date = datetime.now().date() - timedelta(days=30)
                print(f"   ⚠️ Brak daty umowy, startuję od: {start_date}")

            # OBIS
            obis_imp = next((o['obis'] for o in mp.get("meterObjects", []) if o['obis'].startswith("1-0:1.8.0")), None)
            obis_exp = next((o['obis'] for o in mp.get("meterObjects", []) if o['obis'].startswith("1-0:2.8.0")), None)

        # 3. PĘTLA Z HAMULCEM
        print(f"\n3. ROZPOCZYNAM TEST NA {TEST_DAYS_COUNT} DNIACH...")
        
        for i in range(TEST_DAYS_COUNT):
            target_day = start_date + timedelta(days=i)
            
            # === HAMULEC ===
            print(f"\n   🛑 [HAMULEC] Czekam 1.5s przed dniem {i+1}/{TEST_DAYS_COUNT}...")
            await asyncio.sleep(1.5) 
            # ===============
            
            print(f"   🚀 Pobieram dzień: {target_day} ... ", end="", flush=True)
            
            try:
                ts_ms = int(datetime(target_day.year, target_day.month, target_day.day).timestamp() * 1000)
                
                # Tylko jedno zapytanie na dzień dla testu (Pobór)
                p_chart = {
                    "meterPoint": meter_id, 
                    "type": "DAY", 
                    "meterObject": obis_imp, 
                    "mainChartDate": str(ts_ms)
                }
                if token: p_chart["token"] = token
                
                async with session.get(f"{BASE_URL}/resources/mchart", params=p_chart, headers=HEADERS, ssl=False) as r:
                    if r.status == 200:
                        d = await r.json()
                        vals = []
                        if d.get("response") and d["response"].get("mainChart"):
                            vals = [ (p.get("zones", [0])[0] or 0.0) for p in d["response"]["mainChart"] ]
                        
                        print(f"✅ OK! (Suma: {sum(vals):.2f} kWh)")
                    else:
                        print(f"❌ Błąd HTTP {r.status}")
                        print(await r.text())
                        break

            except Exception as e:
                print(f"\n❌ WYJĄTEK (BAN?): {e}")
                break

        print("\n✅ TEST ZAKOŃCZONY. Jeśli widzisz ten napis, mechanizm anti-ban działa.")

if __name__ == "__main__":
    asyncio.run(main())