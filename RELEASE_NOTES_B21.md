## ⚠️ CRITICAL FIX - Update Immediately if on beta.19 or beta.20

**Reverted the "Source Switch"** introduced in beta.19/20.

### Problem
Mapping main sensors to daily chart data (which resets at midnight) violated Home Assistant's `TOTAL_INCREASING` semantics, causing massive negative spikes (~-24,000 kWh) in the Energy Dashboard at midnight.

### Solution
Main sensors (`import_total`, `export_total`) now correctly use lifetime counter data (`total_plus`, `total_minus`) again.

### For Users on beta.19/20
1. **Download** the `repair_midnight_spike.py` script from this release
2. **Stop** Home Assistant
3. **Run** the repair script to clean up corrupted statistics
4. **Update** to beta.21 via HACS
5. **Restart** Home Assistant

### Note
Daily sensors (`daily_pobor`, `daily_produkcja`) remain available for users who need real-time daily data views. These should be used for informational purposes, not for Energy Dashboard tracking.
