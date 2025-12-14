# Changelog

All notable changes to this project will be documented in this file.

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
