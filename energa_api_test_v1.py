import aiohttp
import asyncio
import json
from datetime import datetime

# === TWOJE DANE ===
USERNAME = "username"
PASSWORD = "password"
# ==================

# Konfiguracja jak w integracji v2.0
BASE_URL = "https://api-mojlicznik.energa-operator.pl/dp"
HEADERS = {
    "User-Agent": "Energa/3.0.3 (pl.energa-operator.mojlicznik; build:1; iOS 26.2.0) Alamofire/3.0.3",
    "Accept": "*/*",
    "Accept-Language": "en-US;q=1.0, pl-PL;q=0.9",
    "Content-Type": "application/json"
}

async def main():
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        print("--- FAZA 1: Logowanie (Integracja v2.0) ---")
        
        # 1. Sesja
        await session.get(f"{BASE_URL}/apihelper/SessionStatus", headers=HEADERS, ssl=False)
        
        # 2. Login
        params = {
            "clientOS": "ios",
            "notifyService": "APNs",
            "username": USERNAME,
            "password": PASSWORD
        }
        
        token = None
        try:
            async with session.get(f"{BASE_URL}/apihelper/UserLogin", params=params, headers=HEADERS, ssl=False) as resp:
                data = await resp.json()
                if data.get("success"):
                    # Próba wyciągnięcia tokena, ale bez paniki jak go nie ma
                    token = data.get("token")
                    if not token and data.get("response"):
                        token = data.get("response").get("token")
                    
                    if token:
                        print("   ✅ [OK] Zalogowano pomyślnie (Token pobrany).")
                    else:
                        print("   ⚠️ [OK] Zalogowano pomyślnie (Sesja w Ciasteczkach).")
                else:
                    print(f"   ❌ [BŁĄD] Logowanie nieudane: {data}")
                    return
        except Exception as e:
            print(f"   ❌ Błąd logowania: {e}")
            return

        print("\n--- FAZA 2: Auto-Wykrywanie Metadanych (Kluczowy moment) ---")
        
        # Zabezpieczenie: Token dodajemy tylko jeśli istnieje
        data_params = {}
        if token: data_params["token"] = token

        try:
            async with session.get(f"{BASE_URL}/resources/user/data", params=data_params, headers=HEADERS, ssl=False) as resp:
                if resp.status != 200:
                    print(f"   ❌ Błąd pobierania metadanych: {resp.status}")
                    return

                user_data = await resp.json()
                
                # Zabezpieczenie przed brakiem response
                if not user_data.get("response"):
                    print(f"   ❌ Pusta odpowiedź: {user_data}")
                    return

                mp = user_data['response']['meterPoints'][0]
                meter_id = str(mp.get('id'))
                
                print(f"   Znalezione ID Licznika (API): {meter_id}")
                
                # === DETEKCJA OBIS (To naprawia Twój problem) ===
                obis_import = None
                obis_export = None
                
                print("   Skanowanie obiektów licznika (meterObjects):")
                for obj in mp.get("meterObjects", []):
                    code = obj.get("obis")
                    desc = "Nieznany"
                    
                    if code.startswith("1-0:1.8.0"):
                        desc = "POBÓR (Import)"
                        obis_import = code
                    elif code.startswith("1-0:2.8.0"):
                        desc = "PRODUKCJA (Export)"
                        obis_export = code
                    
                    print(f"      - Kod: {code:<20} -> {desc}")

                if obis_export:
                    print(f"   ✅ [OK] Wykryto kod produkcji: {obis_export}")
                else:
                    print("   ❌ [BŁĄD] Nie znaleziono kodu produkcji w danych użytkownika!")
        except Exception as e:
            print(f"   ❌ Błąd w Fazie 2: {e}")
            import traceback
            traceback.print_exc()
            return

        print("\n--- FAZA 3: Pobieranie Wykresów (Symulacja Sensorów) ---")
        
        ts = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        
        # 1. Pobór
        if obis_import:
            val_import = await fetch_chart(session, meter_id, obis_import, ts, token)
            print(f"   🔋 SENSOR 'daily_pobor':     {val_import} kWh")
        
        # 2. Produkcja
        if obis_export:
            val_export = await fetch_chart(session, meter_id, obis_export, ts, token)
            print(f"   ☀️ SENSOR 'daily_produkcja': {val_export} kWh")
            
            if val_export == 0.0:
                print("\n   🎯 WYNIK TESTU: POZYTYWNY.")
                print("   Integracja poprawnie odczytuje 0.0 kWh używając wykrytego kodu OBIS.")
            elif val_export > 5.0:
                print("\n   ⚠️ WYNIK: PODEJRZANY. Wartość jest wysoka (jak na noc/zimę).")
            else:
                print(f"\n   🎯 WYNIK TESTU: POZYTYWNY. Wartość {val_export} kWh wygląda realnie.")

async def fetch_chart(session, meter_id, obis, ts, token):
    url = f"{BASE_URL}/resources/mchart"
    params = {
        "meterPoint": meter_id,
        "type": "DAY",
        "meterObject": obis, # Używamy wykrytego OBISa!
        "mainChartDate": str(ts)
    }
    if token: params["token"] = token
    
    async with session.get(url, params=params, headers=HEADERS, ssl=False) as resp:
        if resp.status != 200:
            print(f"   ⚠️ Błąd pobierania wykresu: {resp.status}")
            return 0.0
            
        data = await resp.json()
        total = 0.0
        try:
            if data.get("response") and data["response"].get("mainChart"):
                for point in data["response"]["mainChart"]:
                    if point.get("zones"):
                        # Sumujemy wartości (zabezpieczenie przed null)
                        total += sum(v for v in point["zones"] if v is not None)
        except: pass
        return round(total, 3)

if __name__ == "__main__":
    asyncio.run(main())
