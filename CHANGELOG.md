# Changelog

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
