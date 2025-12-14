# Changelog

All notable changes to this project will be documented in this file.

## [v3.5.23] - 2025-12-14

### Changed ⚙️
- **Nuclear Option v3:** Rotated unique IDs for main sensors to `_v3`. This forces Home Assistant to create fresh entities, instantly "cleaning" old corrupted history spikes without requiring complex database operations or finding hidden "trash bin" buttons.

## [v3.5.22] - 2025-12-14

### Changed ⚙️
- **Safe Anchor Validation:** The import logic now strictly validates that the "Anchor" (current total meter reading) is greater than 0. If the API returns 0 or fails to provide a value, the import for that specific metric is **skipped** with a warning notification. This prevents the "25,000 kWh spike" caused by calculating history backwards from zero.

## [v3.5.21] - 2025-12-14

### Fixed 🐛
- **Crash Protection:** Added robust fallback logic if `run_history_import` receives a string ID instead of a data dictionary (fixes missing notifications issue).
- **Import Reliability:** Wrapped the entire import process in a top-level `try-except` block to capture and notify about any crashes.

## [v3.5.20] - 2025-12-14

### Changed ⚙️
- **Expanded Import Scope:** Support for importing "Today's" data. The import loop now fetches data up to the current moment (as far as API allows), ensuring gaps are filled up to the current live readings.
- **Diagnostic History:** Import now also populates statistics for `Energa Pobór Dziś` (Import Today) and `Energa Produkcja Dziś` (Export Today). This allows for diagnostic inspection of exactly what hourly data the API is returning in chart format.
- **Reverted Strict Checks:** Removed the strict abort logic from v3.5.19 that prevented import if reference data was missing. Reverted to robust warnings (Soft Fail) to ensure import proceeds even with partial API data.

## [v3.5.19] - 2025-12-14

### Fixed 🐛
- **Authentication:** Fixed critical login failure ("No token") by supporting cookie-based authentication.
- **History Import:** Removed `_v2` suffix from sensors. History backfill now correctly targets the live sensors.
- **Cleanup:** Simplified sensor logic and removed redundant code.

## [v3.5.17] - 2025-12-14

### New Features 🚀
- **Smart History Import:** The import logic has been completely rewritten. It now calculates historical statistics backwards from the current meter reading. This eliminates data spikes and ensures seamless continuity between imported history and live data.
- **Friendly Notifications:** Notifications now display the Meter Serial Number (e.g., "300302") instead of the internal technical ID.

### Fixed 🐛
- **Data Spikes:** Resolved the issue where history import (starting from 0) clashed with live sensors (starting from ~25k), causing massive spikes in the Energy Dashboard.
- **Sensor Mapping:** Reverted `Energa Import (Panel Energia)` to track Total Meter Reading (`total_increasing`), which is the correct behavior for Energy Dashboard.

### ⚠️ Important / Ważne
**Before using the new import:** You must clear old statistics to remove previous data spikes. See **README** for the "Fixing Data Spikes" procedure.

## [v3.5.16] - 2025-12-14

### Fixed 🐛
- **Notification Crash:** Fixed a critical bug where the new notification system caused the history import to crash immediately.

## [v3.5.15] - 2025-12-14

### New Features 🚀
- **History Import Notifications:** Added system notifications (Persistent Notifications) that inform you when the history download starts and finishes, including a count of processed days.

## [v3.5.14] - 2025-12-14

### UX Improvements 🎨
- **Renamed Sensors:** To prevent confusion, the main Energy Dashboard sensors have been renamed to `Energa Import (Panel Energia)` and `Energa Export (Panel Energia)`. They are also marked as `Diagnostic` to keep the main device view clean, but remain fully selectable in the Energy Dashboard.

## [v3.5.13] - 2025-12-14

### Fixed 🐛
- **Data Spike on History Import:** Resolved an issue where importing history (backfill) would incorrectly overwrite the live sensor state with a cumulative sum. This caused massive data spikes ("sharks") in the Energy Dashboard at the moment of import. The import now correctly populates only the statistics database in the background.

### Refactor 🛠️
- **Code Cleanup:** Moved sensor configuration to `const.py` for better maintainability.
- **Error Handling:** Improved error handling in API calls to prevent silent failures and ensure meaningful logs when Energa API returns unexpected data.
- **Type Hinting:** Added type definitions across the codebase for improved stability and development experience.

## [v3.5.5]
- **Sensor IDs:** Standardized Entity IDs (e.g., `sensor.energa_import_total`) to prevent database corruption.
- **Energy Dashboard:** Introduced `_total` sensors specifically for stable statistics.
