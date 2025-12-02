import requests
import json
import urllib3

# Wyłączamy ostrzeżenia SSL 
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- DANE UŻYTKOWNIKA ---
BASE_URL = "https://api-mojlicznik.energa-operator.pl"
USERNAME = "twojlogin@"  # --- uzupełnij
PASSWORD = "haslo"   # --- uzepełnij

# --- token z telefonu - to może być losowy ciąg znaków 
DEVICE_TOKEN = "5f3fff9554d0eaa1907925ccd9050821d26b9facc42561200e90c0a79e22677f"

HEADERS = {
    'User-Agent': 'Energa/3.0.3 (pl.energa-operator.mojlicznik; build:1; iOS 26.2.0) Alamofire/3.0.3',
    'Accept-Language': 'en-US;q=1.0, pl-PL;q=0.9',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip;q=1.0, compress;q=0.5'
}

def test_new_api():
    print(f"--- ROZPOCZYNAM TEST API DLA: {USERNAME} ---")
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. LOGOWANIE GET
    login_url = f"{BASE_URL}/dp/apihelper/UserLogin"
    params = {
        "clientOS": "ios",
        "notifyService": "APNs",
        "password": PASSWORD,
        "token": DEVICE_TOKEN,
        "username": USERNAME
    }

    print(f"\n1. Próba logowania do: {login_url} ...")
    try:
        # weryfikacja
        resp = session.get(login_url, params=params, verify=False, timeout=20)
        
        print(f"   Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            print("   >>> LOGOWANIE UDANE! Sesja nawiązana.")
            # Wypiszmy ciastka dla pewności
            print(f"   Ciastka sesyjne: {session.cookies.get_dict()}")
        else:
            print("   [!] Błąd logowania.")
            print("   Odpowiedź:", resp.text)
            return

        # 2. POBRANIE DANYCH (resources/user/data)
        data_url = f"{BASE_URL}/dp/resources/user/data"
        print(f"\n2. Pobieranie danych licznika z: {data_url} ...")
        
        resp_data = session.get(data_url, verify=False, timeout=20)
        
        if resp_data.status_code == 200:
            json_data = resp_data.json()
            print("   >>> SUKCES! POBRANO DANE JSON.")
            
            # 3. Szukamy A+ i A-
            try:
                meter = json_data['response']['meterPoints'][0]
                measurements = meter['lastMeasurements']
                
                print("\n--- ODCZYTANE WARTOŚCI ---")
                print(f"PPE: {meter.get('dev')}")
                print(f"Taryfa: {meter.get('tariff')}")
                
                for m in measurements:
                    zone = m.get('zone')
                    val = m.get('value')
                    date = m.get('date')
                    print(f"   Strefa: {zone:15} | Stan: {val} kWh | Data: {date}")
                    
                print("\nTest zakończony sukcesem. Możemy budować integrację.")
                
            except Exception as e:
                print(f"   [!] Błąd parsowania JSON: {e}")
                print("   Surowe dane:", json.dumps(json_data, indent=2)[:500])
        else:
            print(f"   [!] Błąd pobierania danych. Kod: {resp_data.status_code}")

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Wyjątek połączenia: {e}")

if __name__ == "__main__":
    test_new_api()
