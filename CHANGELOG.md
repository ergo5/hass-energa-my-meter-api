# Changelog

## v3.6.0-beta.21 (2025-12-21)
*   **CRITICAL FIX:** Reverted the "Source Switch" introduced in beta.19/20.
*   **Problem:** Mapping main sensors to daily chart data (which resets at midnight) violated Home Assistant's `TOTAL_INCREASING` semantics, causing massive negative spikes in the Energy Dashboard.
*   **Solution:** Main sensors (`import_total`, `export_total`) now correctly use lifetime counter data (`total_plus`, `total_minus`) again.
*   **For Users on beta.19/20:** Use the provided `repair_midnight_spike.py` script to clean up corrupted statistics, then upgrade to beta.21.
*   **Note:** Daily sensors (`daily_pobor`, `daily_produkcja`) remain available for users who need real-time daily data views.

## v3.6.0-beta.20 (2025-12-20)
*   **Improvement:** Implemented Dynamic Versioning. `sensor.py` no longer contains a hardcoded version string; it now fetches the version directly from `manifest.json`. This ensures Device Info in Home Assistant always reflects the installed version.
*   **Maintenance:** Removed redundant imports and cleaned up code.

## v3.6.0-beta.19 (2025-12-20)
*   **DEPRECATED - DO NOT USE:** This version contained a flawed "Source Switch" that caused midnight reset spikes. Update to beta.21 immediately.
