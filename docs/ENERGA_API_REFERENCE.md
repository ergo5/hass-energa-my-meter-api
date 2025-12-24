# Energa API - Modus Operandi

Dokumentacja nieoficjalnego API Energa Mój Licznik na podstawie reverse-engineering.

---

## Endpointy

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/dp/apihelper/SessionStatus` | GET | Inicjalizacja sesji (wymagane przed loginem) |
| `/dp/apihelper/UserLogin` | GET | Logowanie użytkownika |
| `/dp/resources/user/data` | GET | Dane użytkownika, liczniki, pomiary |
| `/dp/resources/mchart` | GET | Dane wykresu (historia godzinowa) |

**Base URL:** `https://api-mojlicznik.energa-operator.pl`

---

## Autentykacja

### Parametry logowania
```
clientOS=ios
notifyService=APNs
username=<email>
password=<hasło>
token=<device_token>  // 64-znakowy hex, generowany per-instalacja
```

### Device Token
- Musi być unikalny per-instalacja
- Generowany: `secrets.token_hex(32)`
- Przechowywany w config entry HA
- **Krytyczne**: bez device_token re-login nie działa!

### Sesja
- Cookies: `JSESSIONID`, `TS015b8f91`
- Token może być pusty w nowszych wersjach API
- Sesja wygasa - wymagany re-login (status 401/403)

---

## Struktura odpowiedzi `/user/data`

### response.meterPoints[]
Główna tablica liczników.

```json
{
  "id": "339038",           // meter_point_id
  "name": "Warszawska 1/1", // custom lub nr licznika
  "dev": "35166491",        // numer seryjny licznika
  "tariff": "G11",
  "agreementPoints": [{     // ⚠️ NOWE API - zagnieżdżone!
    "code": "590243xxx..."  // numer PPE
  }],
  "lastMeasurements": [{
    "zone": "A+ strefa 1",
    "value": 51.989,        // total_plus (import)
    "date": "1766530800000"
  }, {
    "zone": "A- strefa 1",  // TYLKO prosumenci!
    "value": 26627.646      // total_minus (export)
  }],
  "meterObjects": [{
    "obis": "1-0:1.8.0*255", // import
    "label": "DATA.PANEL.ENERGY.A.PLUS"
  }, {
    "obis": "1-0:2.8.0*255", // export (prosumenci)
    "label": "Energia wyprodukowana"
  }]
}
```

### response.agreementPoints[] (stare API)
W starszych wersjach API na poziomie głównym, z adresem.

```json
{
  "id": "339038",
  "code": "590243xxx...",
  "address": "ul. Przykładowa 1, 00-000 Miasto",
  "dealer": { "start": 1749648681282 }
}
```

---

## Różnice: Konsument vs Prosument

| Właściwość | Konsument | Prosument |
|------------|-----------|-----------|
| `total_minus` | NULL/brak | wartość float |
| `A- strefa 1` | brak | present |
| `obis 1-0:2.8.0*255` | present ale bez danych | present z danymi |
| Bilansowanie | brak | BP chart dostępny |

---

## Chart API (`/resources/mchart`)

### Parametry
```
meterPoint=339038
type=DAY
meterObject=1-0:1.8.0*255
mainChartDate=1766530800000  // timestamp dnia 00:00
token=<optional>
```

### Odpowiedź
```json
{
  "response": {
    "mainChart": [
      { "zones": [0.11] },  // godzina 00:00-01:00
      { "zones": [0.101] }, // godzina 01:00-02:00
      // ... 24 punkty
    ]
  }
}
```

### Uwagi
- 24 punkty = pełny dzień
- 22-23 punkty = dzień bieżący (jeszcze niekompletny)
- Pusta odpowiedź = brak danych lub nieaktywny licznik
- Dla A- (export) konsumenci zwracają puste dane

---

## Znane problemy

### 1. Token expiry
- Sesja wygasa po ~kilku godzinach
- API zwraca 401/403
- Wymagany pełny re-login z device_token

### 2. Multi-meter PPE
- Stare API: `agreementPoints` na poziomie głównym
- Nowe API: `agreementPoints` zagnieżdżone w `meterPoint`
- Fallback potrzebny dla kompatybilności

### 3. Brak adresu
- W nowym API konsumenckim brak pola `address`
- Workaround: użycie `name` jako fallback

### 4. 500 Internal Server Error
- Sporadyczne błędy serwera
- Retry z exponential backoff

---

## User-Agent

```
Energa/3.1.2 (pl.energa-operator.mojlicznik; build:1; iOS 16.6.1) Alamofire/5.6.4
```

Ważne: API może odrzucać requesty z innym UA.

---

## Limity

- Rate limiting: nie zidentyfikowane dokładnie
- Obserwowane: 429 przy intensywnych zapytaniach
- Rekomendacja: max 1 req/sek

---

*Ostatnia aktualizacja: 2025-12-24*
