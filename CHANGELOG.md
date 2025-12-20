# Changelog

## v3.6.0-beta.19 (2025-12-20)
*   **Fix:** Changed data source for main "Energy Panel" sensors (`import_panel_energia`). They now fetch data from the **Daily Chart** (which is always up-to-date) instead of the Main Meter endpoint (which often lags 1-3 days).
*   This change fixes the missing "live" bars in the Energy Dashboard, ensuring correct alignment with the official Energa app.
*   The "Meter Counter" sensor (`stan_licznika_pobor`) still shows the raw meter index (total) from the API.
*   **Fix:** Adjusted "Strict Zero Guard" to allow zero readings for daily sensors (where 0 is valid at midnight), while still blocking erroneous zeros for total counters (Lifetime).
*   **Hotfix:** Fixed SyntaxError in `sensor.py` that caused unavailability.

## v3.6.0-beta.18 (2025-12-20)
*   **Fix:** Implemented "Strict Zero Guard" logic. The integration now **rejects "0" readings from the API** during initialization if no history exists, preventing 0->24000 initialization spikes.

## v3.6.0-beta.17 (2025-12-20)
*   **Fix:** Added "Zero Guard" implementation in `sensor.py`.
