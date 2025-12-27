# Changelog

## v4.2.0 (2025-12-27) - Cost Statistics Fixes & Documentation

> **Note:** This is a **minor release** after v4.1.0, including critical bugfixes and comprehensive documentation improvements.

### 🐛 Critical Bug Fixes

#### 1. NULL Timestamps in Cost Statistics

**Problem:** Cost statistics were being imported to the database but with NULL `start_ts` timestamps, 
making them invisible in the Energy Dashboard (0.00 zł displayed for all periods).

**Root Cause:**

The issue was caused by incorrect creation of `StatisticData` objects in the `build_statistics()` function:

```python
# WRONG - Constructor syntax creates object, not TypedDict
StatisticData(start=datetime_obj, sum=value, state=value)

# CORRECT - Plain dict, as expected by Home Assistant's internal API
{"start": datetime_obj, "sum": value, "state": value}
```

Home Assistant's `StatisticData` is defined as a `TypedDict` (in `homeassistant/components/recorder/models/statistics.py`).
When called as a constructor like `StatisticData(...)`, Python does NOT create a dict - it creates a TypedDict 
type hint object. The internal HA code in `db_schema.py` uses `stats["start"].timestamp()` to convert the 
datetime to a Unix timestamp. When `stats` is not a proper dict, this access fails silently and `start_ts` 
becomes NULL.

**Solution:**
- Changed from `StatisticData(...)` constructor to plain dict `{...}` format
- Added `homeassistant.util.dt` import for proper timezone handling
- Used `dt_util.as_utc()` for UTC timezone conversion

#### 2. Incorrect Meter ID in Entity Names

**Problem:** Historical statistics were imported under wrong sensor names (e.g. `sensor.energa_123456_*` 
stead of `sensor.energa_12345678_*`), causing Energy Dashboard to show only partial data.

**Root Cause:**

The `_import_meter_history()` function was using `meter["meter_point_id"]` for building entity IDs:

```python
# WRONG - meter_point_id is API-internal identifier (e.g. 123456)
meter_id = meter["meter_point_id"]
entity_id = f"sensor.energa_{meter_id}_energa_zuzycie"
```

Two identifiers exist in meter data:
- `meter_point_id` (e.g. 123456) - API-internal identifier for communication
- `meter_serial` (e.g. 12345678) - Real meter number visible to user

**Solution:**
- Separated the two identifiers:
  - `meter_point_id` - used only for API calls (`async_get_history_hourly()`)
  - `meter_serial` - used for building user-facing entity IDs
- This matches the original v4.0.2 logic

### 🔧 Additional Fixes
- Fixed Energy Dashboard entity references (removed incorrect `_2` suffix from cost sensor names)
- Updated dictionary access pattern from attribute notation (`.start`, `.state`) to key notation (`["start"]`, `["state"]`)
- Added token expiry handling in Options Flow history import
- Renamed "Reimportuj Statystyki" button to "Wyczyść Statystyki Panelu Energia" for clarity

### 📝 Files Modified
- `__init__.py` - Fixed StatisticData creation, timezone handling, and meter ID usage
- `config_flow.py` - Added token expiry handling, renamed clear_stats button
- `translations/pl.json` - Updated Polish translations
- `translations/en.json` - Added missing English translations

---

## v4.0.2 (2025-12-22) - STABLE RELEASE

**This is a complete rewrite of the integration (Clean Rebuild).**

### 🚀 Key Changes
*   **Architecture:** Simplified sensor logic. Split into "Live Sensors" (for viewing current data) and "Statistics Sensors" (invisible, strictly for Energy Dashboard).
*   **Statistics Repair:** Implemented "Anchor-Based Backward Calculation". Statistics are now calculated by taking the *current* meter reading and subtracting hourly values backwards. This guarantees that **cumulative sums in Home Assistant always match the physical meter reading**, eliminating "negative spikes" and data corruption.
*   **Self-Healing:** The "Download History" (Pobierz Historię) tool now acts as a **repair mechanism**. If your Energy Dashboard shows incorrect spikes, running "Download History" will overwrite the bad data with correctly calculated statistics.

### ✨ New Features
*   **6 Sensors:** 
    *   `Import Total` & `Export Total` (Live readings)
    *   `Daily Import` & `Daily Export` (Live daily counters)
    *   `Panel Energia Import` & `Panel Energia Export` (Invisible, for Dashboard only)
*   **Options Flow:** Configure credentials and run history import directly from Integration Settings.

### 🐛 Bug Fixes
*   Fixed critical bug where `api.py` was generating cumulative sums starting from 0, causing massive spikes when compared to lifetime totals.
*   Fixed `AwesomeVersion` comparison error.
*   Fixed "Unknown" state for live sensors by adding proper `SensorEntity` inheritance.

### 🧹 Cleanup
*   Removed all beta simulation scripts and legacy debug tools.
*   Removed complex "source switching" logic - v4.0 uses a single, robust source of truth.

---

## v3.x Legacy
*   Archived. Please upgrade to v4.0.2 and run "Download History" to clean up your database.
