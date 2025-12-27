<div align="center">
  <img src="logo.png" alt="Energa Mobile API Logo" width="300"/>
</div>

<h1 align="center">Energa Mobile Integration for Home Assistant</h1>


![Version](https://img.shields.io/badge/version-v4.1.1-green)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A robust integration for **Energa Operator** in Home Assistant. It downloads data from the "Mój Licznik" service (Energa Operator) and integrates seamlessly with the **Energy Dashboard**. Features **self-healing history import**, **automatic cost calculation**, and correct cumulative statistics.

---

## ✨ Key Features

*   **📊 Energy Dashboard Ready:** Dedicated sensors (`Panel Energia`) designed specifically for correct statistics.
*   **💰 Automatic Cost Calculation:** Calculates energy costs in PLN based on configured prices.
*   **🛡️ Anchor-Based Statistics:** Calculates history backwards from the current meter reading to guarantee perfect data continuity.
*   **⚡ Hourly Granularity:** Precise hourly consumption/production tracking.
*   **🛠️ Auto-Repair (Self-Healing):** The "Download History" feature automatically fixes gaps and corrupted data.
*   **🔍 OBIS Auto-Detect:** Automatically identifies usage (1.8.0) and production (2.8.0).

---

## 💰 Cost Calculation

The integration **automatically calculates energy costs** and displays them in the Energy Dashboard in **PLN (złoty)**.

**How it works:**
- When you configure energy prices (see below), the integration creates cost sensors
- Cost sensors: `*_energa_zuzycie_cost` (consumption), `*_energa_produkcja_cost` (production)
- These sensors work seamlessly with the Energy Dashboard to show costs alongside energy usage

> [!NOTE]
> **Current Limitation:** Only **fixed prices** are supported. Dynamic pricing (time-of-use tariffs) has not been tested.

---

## 📦 Installation

### Option 1: HACS (Recommended)
1.  Open **HACS** -> **Integrations** -> **Custom repositories**.
2.  Add URL: `https://github.com/ergo5/hass-energa-my-meter-api`
3.  Category: **Integration**.
4.  Install **Energa Mobile Integration** and restart Home Assistant.

### Configuration
1.  Go to **Settings** -> **Devices & Services**.
2.  Add Integration -> Search for **Energa Mobile**.
3.  Login With your **Energa Mój Licznik** credentials.

---

## ⚙️ Price Configuration

To enable cost calculation, you must configure energy prices:

1. Go to **Settings** → **Devices & Services** → **Energa Mobile**
2. Click **Configure** (three dots menu)
3. Select **"Set Energy Prices"** (Ustaw Ceny Energii)
4. Enter your prices:
   - **Consumption (Import)**: Default 1.188 PLN/kWh
   - **Production (Export/Return)**: Default 0.95 PLN/kWh

> [!TIP]
> These prices should match your energy contract rates. You can update them anytime through the same menu.

---

## 📡 Available Sensors

The integration creates multiple sensors organized by function:

### Energy Dashboard Sensors (Panel Energia)
**Use these for the Energy Dashboard:**

| Sensor Name | Description | Purpose |
|-------------|-------------|---------|
| `Energa [ID] Panel Energia Zużycie` | Cumulative consumption | Grid Consumption in Dashboard |
| `Energa [ID] Panel Energia Produkcja` | Cumulative production | Return to Grid in Dashboard |
| `Energa [ID] Panel Energia Zużycie Cost` | Consumption cost (PLN) | Auto-created for cost tracking |
| `Energa [ID] Panel Energia Produkcja Cost` | Production compensation (PLN) | Auto-created for cost tracking |

### Daily Sensors
| Sensor Name | Description |
|-------------|-------------|
| `Energa [ID] Zużycie Dziś` | Today's consumption (kWh) |
| `Energa [ID] Produkcja Dziś` | Today's production (kWh) |

### Meter State Sensors
| Sensor Name | Description |
|-------------|-------------|
| `Energa [ID] Stan Licznika Import` | Total meter reading (consumption) |
| `Energa [ID] Stan Licznika Export` | Total meter reading (production) |

### Metadata Sensors
| Sensor Name | Description |
|-------------|-------------|
| `Energa [ID] Adres` | Installation address |
| `Energa [ID] Taryfa` | Tariff type (e.g., G11) |
| `Energa [ID] PPE` | PPE identification number |
| `Energa [ID] Numer Licznika` | Meter serial number |
| `Energa [ID] Data Aktywacji` | Mój Licznik app activation date* |

*Only available for prosumer accounts

---

## 📊 Energy Dashboard Setup

To see correctly calculated statistics **and costs** in the Energy Dashboard, you MUST select the specific sensors labeled with **"(Panel Energia)"**.

### Step 1: Configure Grid Consumption

| Dashboard Section | Correct Sensor | Cost Sensor |
| :--- | :--- | :--- |
| **Grid Consumption** (Pobór z sieci) | **Energa [ID] Panel Energia Zużycie** | **Energa [ID] Panel Energia Zużycie Cost** |
| **Return to Grid** (Oddawanie do sieci) | **Energa [ID] Panel Energia Produkcja** | **Energa [ID] Panel Energia Produkcja Cost** |

> [!IMPORTANT]
> **Do NOT use:**
> - `Energa Zużycie Dziś` or `Stan Licznika` for the Energy Dashboard
> - Only sensors marked **(Panel Energia)** are designed for statistics

### Step 2: Configure Cost Sensors

When adding energy sources to the Energy Dashboard:
1. Select the **Panel Energia** sensor for energy tracking
2. In the **cost** field, select the corresponding `*_cost` sensor
3. The cost sensor **must match** the energy sensor (e.g., `zuzycie` with `zuzycie_cost`)

> [!NOTE]
> **"Entity Unavailable" (Encja niedostępna)?**
> This is **NORMAL** for statistics sensors (`*_stats`, `*_cost`). They work in background for the Energy Dashboard and don't have a live "state" to display. **They will still work correctly.**

---

## 📅 History Import & Repair

Use this feature if you have missing data OR if you see incorrect spikes in your Energy Dashboard.

1.  Go to **Settings** -> **Devices & Services** -> **Energa Mobile** -> **Configure**.
2.  Select **"Download History"** (Pobierz Historię Danych).
3.  Choose a **Start Date** (e.g., 30 days ago).
4.  Click **Submit**.

**How it works:** The integration downloads fresh data from Energa and calculates clean, continuous statistics based on your current meter reading. This effectively **overwrites** any corrupted historical data, including cost data.

*The process happens in the background. Check logs for progress.*

---

## ⚠️ Limitations

- **Fixed Prices Only:** Dynamic pricing (time-of-use tariffs) is not tested. Only single fixed prices per import/export.
- **PLN Currency:** Cost calculation is in Polish złoty (PLN) only.
- **Statistics Sensors:** Panel Energia sensors may show as "Unavailable" in entity lists (this is normal - they work in Energy Dashboard).
- **Hourly Granularity:** Statistics are hourly - no sub-hour precision.

---

## 🐛 Troubleshooting

### "Token expired" / Authentication Issues

If you see errors like "Token expired, attempting re-login" or frequent authentication failures:

**Solution:** Reinstall and re-add the integration

1. **Update to v4.1.1 or newer** (skip if already on latest):
   - Open **HACS** → **Integrations** 
   - Find **Energa Mobile** → Click **Update** (or **Redownload**)
   - Restart Home Assistant

2. **Remove and re-add configuration**:
   - Go to **Settings** → **Devices & Services** → **Energa Mobile**
   - Click the **3 dots** → **Delete**
   - Add the integration again with your credentials

**Why this helps:** Older versions (before v4.0.9) didn't save the device token properly. Step 1 gets you the fixed code, step 2 saves a persistent token that prevents authentication conflicts.

### Sensors "Panel Energia" Missing?

- Check the **Diagnostic** entities section
- Enable "Show disabled entities" in entity list

### Cost Not Showing in Energy Dashboard?

1. **Verify prices are configured:** Settings → Energa Mobile → Configure → Set Energy Prices
2. **Check cost sensors exist:** Look for `*_cost` sensors in entity list
3. **Ensure correct mapping:** Cost sensor must match energy sensor (e.g., `zuzycie` with `zuzycie_cost`)

### Data Not Appearing in Energy Dashboard?

Ensure you selected the correct `(Panel Energia)` sensors, not the "Daily" or "State" sensors.

### About "Data Aktywacji" Sensor

This sensor shows the **activation date of the Mój Licznik mobile app**, not the contract signing date. It's only available for prosumer (producer-consumer) accounts and may not appear for regular consumer accounts.

---

## 📄 Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

### Disclaimer
This is a custom integration and is not affiliated with Energa Operator. Use at your own risk.
