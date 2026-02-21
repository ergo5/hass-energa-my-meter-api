# Changelog

## v4.4.1 (2026-02-21) - G12w Bugfixes & Code Cleanup

### 🐛 Bug Fixes
- **Statistics spike fix:** `_get_anchor()` was double-counting already-imported data, causing cumulative sum to grow exponentially each coordinator cycle
- **Zero-consumption hours:** `bool(0.0)` evaluates to `False` in Python — hours with 0 kWh were silently skipped. Fixed to `if hourly_value is not None and hourly_value >= 0:`
- **Negative deltas at boundary:** Backward-from-meter_total calculation created negative deltas at the boundary between `fetch_history` and coordinator data
- **Negative sums for new zones:** Backward calculation caused negative sums for newly activated tariff zones (e.g., G12w zone 2 started at -12.886 kWh)
- **Clear stats now includes costs:** `async_clear_statistics()` was missing `_cost` statistic IDs, leaving orphaned cost data

### 🔧 Code Quality
- **Forward-from-zero calculation:** Replaced backward anchor-based calculation with forward-from-zero approach — guarantees monotonically increasing, non-negative sums
- **Deduplicated price logic:** Extracted `get_price_for_key()` helper in `const.py`, replacing identical code in 3 files
- **Rate limiting:** Added 0.3s delay between API requests in coordinator path to prevent throttling
- **Spike guard constant:** Replaced hardcoded `100` with `MAX_HOURLY_KWH` constant, added warning log
- **Dead code cleanup:** Removed unused `resolve_entity_id()`, `_tz`, `UTC` constant, anchor parameters

> **Note:** Forward-from-zero produces identical Energy Dashboard results (HA uses sum differences). No user action required after update.

## v4.4.0 (2026-02-19) - G12w Multi-Zone Tariff Support

### ✨ New Features
- **G12w multi-zone tariff support:** Automatic detection and separate tracking of peak (zone 1) and off-peak (zone 2) consumption
- **Zone-specific pricing:** Configurable prices per zone via Options Flow
- **New sensors for G12w:** `Panel Energia Strefa 1`, `Panel Energia Strefa 2` with corresponding cost sensors
- **Zone-aware history import:** Downloads and imports zone-specific hourly data

### 🔧 Changes
- Options Flow dynamically shows zone-specific or single price fields based on detected meter type
- `clear_stats` extended to include zone-specific statistic IDs

## v4.3.10 (2026-02-13) - Negative Cost Fix

- Fixed: Negative cost values appearing in Energy Dashboard
- Root cause: Cost statistics not being cleared/recalculated when energy statistics were updated
- Affects: Users who previously ran history import and saw negative PLN values

## v4.3.9 (2026-02-11) - Hour Offset Fix

- Fixed: Hourly statistics were shifted +1 hour compared to Energa app
- API index 0 = 00:00-01:00, was incorrectly mapped to 01:00 (now correctly maps to 00:00)
- Affects: Energy Dashboard hourly bars, Panel Energia statistics
- After update: clear statistics and reimport history (30 days) for correct alignment

## v4.3.8 (2026-02-11) - Session Isolation Fix

- Fixed: Use dedicated HTTP session instead of shared HA session
- Prevents `cookie_jar.clear()` from affecting other integrations
- Session properly closed on entry unload and HA shutdown

## v4.3.7 (2026-02-10) - HACS Validation Fix

- Fixed: Removed extra keys from `hacs.json` (only `name`, `render_readme`, `country` allowed)
- Version bump for clean release tag

## v4.3.6 (2026-02-06) - HACS Compliance Release

- Documentation: Native API emphasis in README, English API reference
- Security: Removed sensitive keys and credentials from repository
- Branding: Updated logo and icon to Energa | GRUPA ORLEN identity
- Submitted to HACS default repository (PR #5416)

## v4.3.5 (2026-01-28) - Energy Dashboard Spike Fix

- Synced LAB-verified code to fix remaining Energy Dashboard spikes
- Validated on both prosumer and consumer accounts

## v4.3.4 (2026-01-27) - StatisticsBuilder

- Added `StatisticsBuilder` class for incremental sum calculation
- Prevents negative statistics spikes caused by backup/restore cycles
- Anchor-based backward calculation from current meter reading

## v4.3.3 (2026-01-26) - Negative Statistics Fix

- Resolved negative statistics appearing in Energy Dashboard
- Root cause: sum resets after HA backup restoration
- Statistics now rebuild cleanly from meter totals

## v4.2.4 (2026-01-25) - Entity ID Pattern Fix

- Corrected `entity_id` pattern in history import to match PROD sensors
- Changed from `energa_zuzycie` to `panel_energia_zuzycie` pattern

## v4.2.3 (2025-12-28) - State Class Restoration

- Restored `state_class` for Energy Dashboard compatibility

## v4.2.2 (2025-12-28) - Entity Filter Fix

- Corrected entity_id filter to match `panel_energia_` pattern
- Removed incorrect `_stats` requirement from clear_stats filter

## v4.2.1 (2025-12-27) - Statistics Initialization

- Simplified statistics fix with forward calculation in `build_statistics`
- Removed `state_class` from Panel Energia sensors to prevent UNIQUE constraint errors
- Accepted history catch-up spike as expected behavior on first import

---

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
