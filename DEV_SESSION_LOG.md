# Energa Integration - Analiza Multi-Meter (24.12.2025)

## Kontekst
Użytkownik "kwiateusz" zgłosił problem z dwoma licznikami - PPE i adres są takie same dla obu.

---

## Co wiemy z logów użytkownika

### Meter #1: ID=339038, Serial=35166491
- **name**: "Warszawska 1/1" (custom)
- **total_plus**: 51.989 kWh (A+ strefa 1)
- **total_minus**: BRAK (konsument bez PV!)
- **PPE (zagnieżdżone)**: `590243xxx001076xxx`
- **agreementPoints**: jest WEWNĄTRZ meterPoint (nie na poziomie głównym)
- **address**: BRAK w danych (użytkownik ustawił własną nazwę)

### Meter #2: ID=325938, Serial=11215052
- **name**: "11215052" (domyślna = nr licznika)
- **total_plus**: 3361.886 kWh
- **total_minus**: BRAK (konsument bez PV!)
- **PPE (zagnieżdżone)**: `590xxx63000855xxx` - **INNY niż Meter #1!**
- **agreementPoints**: też WEWNĄTRZ meterPoint
- **address**: BRAK w danych

### Dane historyczne (chart)
- Meter #1: Pobór działa (22-24 punkty/dzień)
- Meter #2: **Brak danych** (wszystkie dni "No chart data")
  - Możliwa przyczyna: nowy licznik, nieaktywny, lub problem API

---

## Zidentyfikowane problemy

### 1. PPE/Address "takie same" - NIEPRAWDA
Z logów widzimy że PPE jest **RÓŻNE** dla każdego licznika.
Użytkownik może widzieć "takie same" bo:
- Nasz kod szukał `agreementPoints` na poziomie głównym (nie znajdował)
- Fallback pobierał pierwszy znaleziony lub pusty

**Fix**: Szukać `agreementPoints` wewnątrz każdego `meterPoint`

### 2. Brak `total_minus` dla konsumentów
Użytkownik jest **konsumentem** (brak eksportu/PV).
API zwraca `total_minus = NULL/BRAK`.

**Fix**: Pattern `meter.get("total_minus") or 0` zamiast `meter.get("total_minus", 0)`
*(dict.get z default nie obsługuje None jako wartości)*

### 3. Brak danych chart dla Meter #2
API zwraca puste dane dla drugiego licznika.
Możliwe przyczyny:
- Licznik nieaktywny
- Brak odczytów zdalnych
- Problem po stronie API Energa

---

## Stan Lab (IP: 192.168.70.199)

- **Konto**: Konsument (znajomego, bez PV)
- **Wersja**: v4.0.9 + fix None handling
- **Sensory Panel Energia**: niedostępne - **TO JEST OK dla konsumenta bez eksportu**
- **Sensory Live** (Zużycie Dziś, Stan Licznika): powinny działać

---

## Aktualny status (09:53)

**Lab (prosument - ciesielski.dominik@gmail.com)**:
- ✅ Integracja v4.0.9 + wszystkie fix-y działa
- ✅ 10 encji dla licznika 30132815
- ✅ Data Aktywacji: `2025-06-11`
- ✅ Zużycie Dziś aktualizuje się poprawnie
- ✅ Błąd `mean_type` naprawiony (StatisticMeanType.NONE)
- ⏳ Czekamy na stabilność przed publikacją

**Wektory dostępu:**
| Wektor | Konfiguracja |
|--------|--------------|
| Dysk Y: | `Y:\custom_components\energa_mobile\` |
| HA API | Token długotrwały, `http://192.168.70.199:8123/api/` |
| SSH | `root@192.168.70.199` hasło: `lab` |

**Skrypty:**
- `tools/ha_api_test.py` - test API
- `tools/ssh_lab.py` - SSH via paramiko
- `tools/get_logs.py` - pobieranie logów HA

**Multi-meter status:**
- ✅ Kod teoretycznie gotowy (nested + top-level PPE)
- ⚠️ Nie przetestowany - brak konta z 2 licznikami
- 📋 Plan: wydać jako beta, poprosić użytkownika o test

**Warningi do ignorowania (HA 2026.11):**
- `unit_class` not specified - OK
- `state_class None` - OK (sensory statystyczne)
- `custom integration not tested` - normalne dla HACS

---

## Changelog

### 2025-12-24 08:19 - Contract Date Sensor Fix ✅
- **api.py**: Przywrócono logikę v4.0.9 z `next()` iterator dla agreementPoints
  - `ag` pochodzi z top-level agreementPoints (ma `dealer.start`)
  - PPE pobierane z nested agreementPoints jeśli dostępne
- **sensor.py**: Dodano `contract_date` do `info_types` (linia 161)
- **WYNIK**: ✅ Sensor "Data Aktywacji" działa!
  - Prosument: `2025-06-11`
  - Konsument: brak (API nie zwraca `dealer.start`)

### 2025-12-24 07:05 - Multi-meter PPE fix
- **api.py**: `_fetch_all_meters()` - szukamy `agreementPoints`:
  1. Wewnątrz `meterPoint` (nowe API)
  2. Fallback na top-level (stare API)
- Adres: używamy `name` jako fallback

### 2025-12-24 06:50 - Przywrócenie v4.0.9 + None fix
- Cofnięto uszkodzone pliki (null bytes z PowerShell redirect)
- Użyto `git checkout v4.0.9` + `Copy-Item -Force`
- Dodano fix `or 0` dla konsumentów

### 2025-12-24 06:35 - ❌ Pierwsza próba multi-meter fix (FAIL)
- Pliki uszkodzone przez `git show > file` (null bytes)
- Integracja się nie ładowała

---

## Do zrobienia

1. [ ] **Restart lab** i test konsumenta
2. [ ] **Test prosumenta** na produkcji
3. [ ] **PR brands** - czeka na review
4. [ ] **Jeśli OK**: publikacja jako v4.1.0

---

## Ważne zasady

- ⏰ **Zasada 24h**: testuj lokalnie przed publikacją
- 🔍 **Konsument vs Prosument**: różne dane API
- 📦 **v4.1.0**: wersja stabilna, multi-meter fix

---

## 📋 Przyszłe ulepszenia (Future Improvements)

### Translations dla sensorów
- **Problem**: Nazwy sensorów (np. "Data Aktywacji") są hardcoded w `sensor.py`
- **Priorytet**: Niski (większość użytkowników to Polacy)
- **Rozwiązanie**: 
  - Dodać sensor name translations do `pl.json` i `en.json`
  - Refactor `info_types` w `sensor.py` aby używać translation keys
- **Uwaga**: Standard HA to hardcoded nazwy - wymaga research czy warto

### Multi-meter adresy
- **Status**: PPE działa poprawnie, adresy to "nice to have"
- **Możliwe rozwiązanie**: Szukać adresu w nested agreementPoints (analogicznie jak PPE)
- **Priorytet**: Niski - użytkownicy identyfikują liczniki po PPE

### unit_class dla HA 2026.11
- **Warning**: `unit_class not specified` w async_import_statistics
- **Kiedy**: Stanie się wymagane w HA 2026.11
- **Action**: Dodać `unit_class` do StatisticMetaData przed końcem 2026

