#!/usr/bin/env python3
"""
Energa API Multi-Meter Test Script
Diagnozuje problem z PPE/adresem dla wielu liczników.

Użycie:
  python energa_multi_meter_test.py <email> <hasło>
  
Przykład:
  python energa_multi_meter_test.py user@example.com MojeHaslo123
"""

import asyncio
import aiohttp
import secrets
import json
import sys

BASE_URL = "https://api-mojlicznik.energa-operator.pl/dp"
SESSION_URL = f"{BASE_URL}/apihelper/SessionStatus"
LOGIN_URL = f"{BASE_URL}/apihelper/UserLogin"
DATA_URL = f"{BASE_URL}/resources/user/data"

HEADERS = {
    "User-Agent": "Energa/3.1.2 (pl.energa-operator.mojlicznik; build:1; iOS 16.6.1) Alamofire/5.6.4",
    "Accept": "application/json",
    "Accept-Language": "pl-PL;q=1.0, en-PL;q=0.9",
    "Content-Type": "application/json",
}

async def main(username: str, password: str):
    print("=" * 60)
    print("Energa API Multi-Meter Test")
    print("=" * 60)
    
    device_token = secrets.token_hex(32)
    
    async with aiohttp.ClientSession() as session:
        # Init session (required before login)
        print("\n[1] Inicjalizacja sesji...")
        async with session.get(SESSION_URL, headers=HEADERS, ssl=False) as resp:
            print(f"    Status: {resp.status}")
        
        # Login
        print("\n[2] Logowanie...")
        login_params = {
            "clientOS": "ios",
            "notifyService": "APNs",
            "username": username,
            "password": password,
            "token": device_token,
        }
        
        async with session.get(LOGIN_URL, headers=HEADERS, params=login_params, ssl=False) as resp:
            print(f"    Status: {resp.status}")
            if resp.status != 200:
                text = await resp.text()
                print(f"    BŁĄD: {text[:500]}")
                return
            try:
                data = await resp.json()
                if not data.get("success"):
                    print(f"    BŁĄD: success=False, {data}")
                    return
                print("    OK - zalogowano")
            except:
                print("    BŁĄD: nieprawidłowa odpowiedź JSON")
                return
        
        # Fetch user data
        print("\n[3] Pobieranie danych użytkownika...")
        async with session.get(DATA_URL, headers=HEADERS, ssl=False) as resp:
            print(f"    Status: {resp.status}")
            if resp.status != 200:
                text = await resp.text()
                print(f"    BŁĄD: {text[:500]}")
                return
            
            data = await resp.json()
        
        # Analyze response structure
        print("\n[3] Analiza odpowiedzi API:")
        print("-" * 60)
        
        # Show top-level keys
        print(f"\nKlucze główne: {list(data.keys())}")
        
        # Find meters
        meters = data.get("meters", [])
        meter_points = data.get("meterPoints", [])
        
        print(f"\nLiczba 'meters': {len(meters)}")
        print(f"Liczba 'meterPoints': {len(meter_points)}")
        
        # Show meter points details
        print("\n" + "=" * 60)
        print("SZCZEGÓŁY PUNKTÓW POBORU (meterPoints):")
        print("=" * 60)
        
        for i, mp in enumerate(meter_points):
            print(f"\n--- Punkt poboru #{i+1} ---")
            print(f"  ID: {mp.get('id')}")
            print(f"  PPE: {mp.get('ppe')}")
            print(f"  Adres: {mp.get('address')}")
            print(f"  Taryfa: {mp.get('tariff')}")
            print(f"  Liczniki w tym punkcie: {mp.get('meters', [])}")
        
        # Show meters details
        print("\n" + "=" * 60)
        print("SZCZEGÓŁY LICZNIKÓW (meters):")
        print("=" * 60)
        
        for i, m in enumerate(meters):
            print(f"\n--- Licznik #{i+1} ---")
            print(f"  ID: {m.get('id')}")
            print(f"  Serial: {m.get('serialNumber') or m.get('meterSerial')}")
            print(f"  meterPointId: {m.get('meterPointId')}")
            print(f"  PPE (bezpośrednio): {m.get('ppe', 'BRAK')}")
            print(f"  Adres (bezpośrednio): {m.get('address', 'BRAK')}")
        
        # Raw JSON for analysis (truncated)
        print("\n" + "=" * 60)
        print("SUROWA ODPOWIEDŹ JSON (do analizy):")
        print("=" * 60)
        print(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Użycie: python energa_multi_meter_test.py <email> <hasło>")
        sys.exit(1)
    
    asyncio.run(main(sys.argv[1], sys.argv[2]))
