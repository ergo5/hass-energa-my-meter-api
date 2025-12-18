# Changelog

## [v3.6.0-beta.10] - 2025-12-18

### Fixed 🐛
- **Self-Healing Crash:** Fixed a critical bug (`NameError: datetime`) that prevented self-healing from running (originally in beta.9).
- **Manual Import Strings:** Fixed an issue where manual history import could fail with "Internal function received STRING". Added forced data refresh to handle this case.
- **Deprecation Warnings:** Fixed `mean_type` not being specified in `async_import_statistics` (future HA compatibility).
- **Stability:** General improvements to error handling during data fetching.




## [v3.6.0-beta.8] - 2025-12-17

### New Features 🚀
- **Circuit Breaker (Safety Mechanism):** Implemented a mandatory **4-hour cooldown** on self-healing attempts.
- **Protection:** If a history repair attempt fails (e.g. because Energa API is down or lagging), the integration will *wait* 4 hours before trying again for that specific meter. This prevents "infinite retry loops" that could get your IP banned by Energa for excessive requests.



## [v3.6.0-beta.7] - 2025-12-17

### Changed ⚙️
- **Faster Updates:** Increased API polling frequency to **30 minutes** (previously 60 min).
- **Responsive Dashboard:** This ensures that as soon as Energa processes the hourly data, Home Assistant fetches it in the next half-hour window, minimizing the delay between "real world" usage and your Energy Dashboard.



## [v3.6.0-beta.6] - 2025-12-17

### New Features 🚀
- **Live Hourly Updates:** Dramatically reduced the "Self-Healing" threshold from 24h to **3h**.
- **Dashboard Friendly:** The integration now continuously checks for new hourly data throughout the day. As soon as Energa publishes the hourly usage (usually with a few hours delay), it is immediately imported into Home Assistant. This ensures the Energy Dashboard bars appear "today" rather than "tomorrow".



## [v3.6.0-beta.5] - 2025-12-17

### New Features 🚀
- **Self-Healing History:** Implemented an automatic "History Health Check" that runs hourly. If the integration detects a data gap (last history entry > 24h old), it automatically triggers a backfill import for the missing days.
- **Smart Gap & Fill:** Logic inspired by alternative integrations; ensures seamless data continuity.

### Fixed 🐛
- **Live Data Logic:** Updated the sensor update loop to check for history gaps immediately after fetching fresh data.


All notable changes to this project will be documented in this file.

## [v3.6.0-beta.1] - 2025-12-14

### Fixed 🐛
- **Graph Drop (Stale Cache):** The import logic now forces a fresh API data fetch (bypassing cache) before calculating history. this resolves issues where the "Anchor" (reference point) was outdated or zero (due to cached Service Calls), causing graph spikes/drops.
- **Deprecation Warnings:** Correctly added `mean_type=None` to `StatisticMetaData` calls, resolving FutureWarnings for Home Assistant 2026.11.

### Changed ⚙️
- **Diagnostics:** Added INFO logging of the exact Anchor values (Import/Export) used for calculation, to aid in verifying data integrity.

## v3.6.0-beta.4
- **HOTFIX:** Fixed `IndentationError` in `__init__.py` introduced in beta.3.
- **RESTORED:** The `if eid_total:` check was accidentally removed, causing the syntax error. It is now restored.
- **Functionality:** Identical to beta.3 (DB fix + Force Refresh), but actually runnable.

## v3.6.0-beta.3
- **CRITICIAL FIX:** Reverted the `mean_type=None` addition causing `sqlite3.IntegrityError` and database crashes during import.
- **NOTE:** This restores the `DeprecationWarning` in logs but ensures data is successfully written to the database.
- **Core Logic:** The `force_refresh=True` fix for graph anchor issues is preserved and should now function correctly as the database write will proceed.

## [v3.6.0-beta.2] - 2025-12-14

### Fixed 🐛
- **Cosmetic:** Updated the hardcoded `sw_version` in `sensor.py` which was stuck on `3.5.23`, causing confusion in the Device Info panel.

## [v3.6.0-beta.1] - 2025-12-14

### Fixed 🐛
- **Paranoid Failure Protection:** Re-implemented the internal 'fail-safe' mechanism inside `run_history_import`. This guarantees that even if Home Assistant passes a raw string ID (found in logs despite previous fixes), the function will self-correct and fetch the necessary data instead of crashing with a `TypeError`.
- **Service Registration:** Forced the `fetch_history` service to re-register on every startup, preventing usage of stale code versions.

## [v3.5.25] - 2025-12-14

### Fixed 🐛
- **Paranoid Failure Protection:** Re-implemented the internal 'fail-safe' mechanism inside `run_history_import`. This guarantees that even if Home Assistant passes a raw string ID (found in logs despite previous fixes), the function will self-correct and fetch the necessary data instead of crashing with a `TypeError`.
- **Service Registration:** Forced the `fetch_history` service to re-register on every startup, preventing usage of stale code versions.

## [v3.5.24] - 2025-12-14

### Fixed 🐛
- **Log Noise:** Resolved invalid `StatisticMetaData` call warnings ("doesn't specify mean_type") by explicitly setting `mean_type` to `None`.
- **Import Failures:** Enhanced the import service to handle string ID inputs from older configs/calls robustly, preventing silent failures.
- **Missing History:** Confirmed alignment of `_v3` entity IDs between sensor creation and history import, ensuring the imported data actually lands in the visible dashboard sensors.

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
