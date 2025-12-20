# Changelog

## v3.6.0-beta.19 (2025-12-20)
*   **Fix:** Zmiana źródła danych dla głównych sensorów "Panel Energia" (`import_panel_energia`). Od teraz pobierają one dane z **Wykresu Dziennego** (który jest zawsze aktualny) zamiast z endpointu Licznika Głównego (który często ma opóźnienia 1-3 dni).
*   Ta zmiana naprawia brak słupków "na żywo" w Panelu Energia, zapewniając zgodność z oficjalną aplikacją Energa.
*   Sensor "Stan Licznika" (`stan_licznika_pobor`) nadal pokazuje surowy stan licznika (total) z API.
*   **Fix:** Dostosowanie "Strict Zero Guard", aby pozwalał na zerowe odczyty dla sensorów dziennych (gdzie 0 jest poprawną wartością o północy), ale nadal blokował błędne zera dla liczników sumarycznych (Lifetime).

## v3.6.0-beta.18 (2025-12-20)
*   **Fix:** Zmiana logiki "Zero Guard" na bardziej restrykcyjną. Od teraz integracja **całkowicie odrzuca odczyty "0" z API**, nawet przy pierwszym uruchomieniu.

## v3.6.0-beta.17 (2025-12-20)
*   **Fix:** Implementacja "Zero Guard" w `sensor.py`.
