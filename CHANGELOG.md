# Changelog

## v3.6.0-beta.18 (2025-12-20)
*   **Fix:** Zmiana logiki "Zero Guard" na bardziej restrykcyjną. Od teraz integracja **całkowicie odrzuca odczyty "0" z API**, nawet przy pierwszym uruchomieniu (gdy nie ma jeszcze historii).
*   Zapobiega to powstawaniu gigantycznych "szpilek" (np. 0 -> 24000 kWh) w dniu instalacji, jeśli API Energy zwróci błędną wartość podczas inicjalizacji.

## v3.6.0-beta.17 (2025-12-20)
*   **Fix:** Implementacja "Zero Guard" w `sensor.py` - ignorowanie spadków do zera (typowe dla błędów API), jeśli poprzednia wartość była poprawna.
*   **Fix:** Zmiana domyślnych wartości w `api.py` z `0.0` na `None`, aby uniknąć fałszywych inicjalizacji.
*   **Update:** Zwiększenie poziomu logowania dla interwencji Zero Guard.

## v3.6.0-beta.16 (2025-12-19)
*   **Fix:** Naprawiono błąd `TypeError: unsupported operand type(s) for +: 'datetime.date' and 'timedelta'`, który występował przy pobieraniu starszej historii.
*   **Fix:** Poprawiono wyświetlanie numeru PPE w `device_info` (wcześniej pokazywało wewnętrzne ID).
*   **Feature:** Dodano skrypt symulacyjny `simulate_wide.py` do testowania długich okresów danych.

## v3.6.0-beta.15 (2025-12-18)
*   **Fix:** Hard-coded `force_refresh=True` in `run_history_import` via fail-safe mechanism inside `api.py` to guarantee fresh data for resolution.
*   **Fix:** Removed strict type check for `meter_data` in `run_history_import` to allow string-based IDs to trigger checking.
*   **Fix:** Added extensive debug logging for Import Service flow.

## v3.6.0-beta.14 (2025-12-18)
*   **Fix:** Reverted `mean_type` parameter in `async_import_statistics` as it is not supported in HA < 2025.x, causing imports to fail silently.
*   **Fix:** Added explicit `force_refresh=True` to `run_history_import` data fetching to prevent stale cache issues during ID resolution.

## v3.6.0-beta.13 (2025-12-18)
*   **Fix:** "Invalid mean type" error during history import. Added `mean_type=None` to `StatisticMetaData` to comply with newer Home Assistant recorder requirements.

## v3.6.0-beta.12 (2025-12-18)
*   **Fix:** `UnboundLocalError`: referenced before assignment failure in `_check_and_fix_history`.
*   **Improvement:** Enhanced self-healing logging.

## v3.6.0-beta.11 (2025-12-18)
*   **New Feature:** Automatic History Backfill (Self-Healing). detect gaps > 3h and trigger import.
*   **Improvement:** Smart "Anchor" logic to connect imported history with live readings seamlessly.
