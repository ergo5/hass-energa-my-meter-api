# Changelog

## v3.6.0-beta.20 (2025-12-20)
*   **Improvement:** Implemented Dynamic Versioning. `sensor.py` no longer contains a hardcoded version string; it now fetches the version directly from `manifest.json`. This ensures Device Info in Home Assistant always reflects the installed version.
*   **Maintenance:** Removed redundant imports and cleaned up code.

## v3.6.0-beta.19 (2025-12-20)
*   **Fix:** Changed data source for main "Energy Panel" sensors (`import_panel_energia`). They now fetch data from the **Daily Chart** (which is always up-to-date) instead of the Main Meter endpoint (which often lags 1-3 days).
*   This change fixes the missing "live" bars in the Energy Dashboard, ensuring correct alignment with the official Energa app.
*   The "Meter Counter" sensor (`stan_licznika_pobor`) still shows the raw meter index (total) from the API.
*   **Fix:** Adjusted "Strict Zero Guard" to allow zero readings for daily sensors (where 0 is valid at midnight), while still blocking erroneous zeros for total counters (Lifetime).
*   **Hotfix:** Fixed SyntaxError in `sensor.py` that caused unavailability.
