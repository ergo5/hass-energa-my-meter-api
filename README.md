<div align="center">
  <img src="logo.png" alt="Energa My Meter API Logo" width="300"/>
</div>

<h1 align="center">Energa My Meter API Integration for Home Assistant</h1>


![GitHub Release](https://img.shields.io/github/v/release/ergo5/hass-energa-my-meter-api)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
![API](https://img.shields.io/badge/data_source-Native_API-blue)

🇵🇱 This integration is designed for customers of **Energa Operator** — a regional electricity distributor serving **northern Poland** (Pomorze, Warmia-Mazury, Kujawsko-Pomorskie).

A robust integration for **Energa Operator** in Home Assistant that communicates directly with the **native REST API** — **not web scraping**. It retrieves data from the "Mój Licznik" portal and integrates seamlessly with the **Energy Dashboard**. Features **self-healing history import**, **automatic cost calculation**, and reliable cumulative statistics.

> [!TIP]
> For technical details about the API endpoints, see [ENERGA_API_REFERENCE.md](docs/ENERGA_API_REFERENCE.md).

---

## ✨ Key Features

*   **📡 Native API:** Direct communication with Energa's REST API — lightweight JSON responses, stable interface.
*   **📊 Energy Dashboard Ready:** Dedicated sensors (`Panel Energia`) designed specifically for correct statistics.
*   **💰 Automatic Cost Calculation:** Calculates energy costs in PLN based on configured prices.
*   **🛡️ Reliable Statistics:** Spike-free Energy Dashboard — data is always consistent.
*   **⚡ Hourly Granularity:** Precise hourly consumption/production tracking.
*   **🔌 Multi-Zone Tariffs (G12/G12w):** Automatic detection of two-zone meters with separate peak/off-peak tracking for both import and export.
*   **⚖️ Prosumer Balance:** Tracks net billing balance with configurable coefficient (default 0.8).
*   **🛠️ Auto-Repair (Self-Healing):** The "Download History" feature automatically fixes gaps and corrupted data.
*   **🔍 Auto-Detect:** Automatically identifies consumption and production meters.

---

## 📦 Installation

### HACS (Recommended)
1.  Open **HACS** → **Integrations**.
2.  Search for **Energa My Meter**.
3.  Click **Install** and restart Home Assistant.

<details>
<summary>Manual Installation</summary>

1. Download the latest release from [GitHub Releases](https://github.com/ergo5/hass-energa-my-meter-api/releases)
2. Copy the `custom_components/energa_mobile` folder to your `config/custom_components/` directory
3. Restart Home Assistant

</details>

### Configuration
1.  Go to **Settings** → **Devices & Services**.
2.  Click **Add Integration** → search for **Energa My Meter**.
3.  Log in with your **Energa Mój Licznik** credentials.

---

## 💰 Cost Calculation

The integration **automatically calculates energy costs** and displays them in the Energy Dashboard in **PLN (złoty)**.

**How it works:**
- When you configure energy prices (see below), the integration creates:
  - **Price sensors** (`Cena Poboru Strefa 1/2`) — diagnostic entities showing the current PLN/kWh rate, used for import cost tracking in the Energy Dashboard
  - **Compensation statistics** (`Rekompensata`) — pre-calculated cumulative export compensation in PLN
- In the Energy Dashboard, import costs are tracked via **"Use entity with current price"** pointing to the price sensor
- Export compensation is tracked via **"Use entity tracking total compensation"** pointing to the Rekompensata entity

> [!NOTE]
> **Two-zone tariffs** (G12, G12w, G12r) are fully supported with separate zone pricing. Three-zone tariffs (G13) are not currently supported.

---

## ⚙️ Price Configuration

To enable cost calculation, you must configure energy prices:

1. Go to **Settings** → **Devices & Services** → **Energa My Meter**
2. Click **Configure** (three dots menu)
3. The options menu will appear with the following choices:

| Menu Option | Description |
|---|---|
| **Set Energy Prices** | Configure PLN/kWh rates for cost calculation |
| **Download History** | Fetch & repair historical hourly data |
| **Clear Energy Panel Statistics** | Wipe all statistics before a fresh re-import |
| **Change Credentials** | Update your Mój Licznik username/password |

### Setting Energy Prices

Select **"Set Energy Prices"** and enter your tariff rates:

| Tariff | Field | Default (PLN/kWh) |
|---|---|---|
| **G11** (single-zone) | Import | 1.188 |
| **G12/G12w** zone 1 (peak) | Import Zone 1 | 1.2453 |
| **G12/G12w** zone 2 (off-peak) | Import Zone 2 | 0.5955 |
| All tariffs | Export | 0.95 |
| All tariffs | Prosumer coefficient | 0.8 (80%) |
| Prosumer accounts | Baseline import [kWh] | 0 |
| Prosumer accounts | Baseline export [kWh] | 0 |

> [!TIP]
> The options form automatically adapts to your tariff — two-zone meters (G12/G12w) will see zone-specific fields, single-zone meters (G11) will see a single import price.

> [!NOTE]
> **Prosumer baseline** (`balance_baseline_import` / `balance_baseline_export`) sets the meter reading at the start of your net billing period. Leave at `0` to calculate the prosumer balance from the beginning of recorded history.

---

## 📋 Available Sensors

The integration creates multiple sensors organized by function:

### Energy Dashboard Sensors (Panel Energia)
**Use these for the Energy Dashboard:**

> [!NOTE]
> Panel Energia sensors show **"unknown"** in the entity list — this is normal. Their data appears only in the **Energy Dashboard**, not as a live state.

#### Single-Zone (G11)

| Sensor Name | Description | Purpose |
|-------------|-------------|---------|
| `Panel Energia Zużycie` | Cumulative consumption | Grid Consumption in Dashboard |
| `Panel Energia Produkcja` | Cumulative production | Return to Grid in Dashboard |
| `Panel Energia Produkcja Rekompensata` | Production compensation (PLN) | Select as export compensation entity in Dashboard |

#### Multi-Zone (G12/G12w) — auto-created for two-zone tariffs

| Sensor Name | Description | Purpose |
|-------------|-------------|---------|
| `Panel Energia Strefa 1` | Peak zone consumption | Zone 1 import in Dashboard |
| `Panel Energia Strefa 2` | Off-peak zone consumption | Zone 2 import in Dashboard |
| `Panel Energia Produkcja Strefa 1` | Peak zone production | Zone 1 export in Dashboard |
| `Panel Energia Produkcja Strefa 2` | Off-peak zone production | Zone 2 export in Dashboard |
| `Panel Energia Produkcja Strefa 1 Rekompensata` | Peak zone compensation (PLN) | Zone 1 export compensation entity |
| `Panel Energia Produkcja Strefa 2 Rekompensata` | Off-peak zone compensation (PLN) | Zone 2 export compensation entity |

### Daily Sensors
| Sensor Name | Description |
|-------------|-------------|
| `Zużycie Dziś` | Today's consumption (kWh) |
| `Produkcja Dziś` | Today's production (kWh) |

### Meter State Sensors
| Sensor Name | Description |
|-------------|-------------|
| `Stan Licznika Import` | Total meter reading (consumption) |
| `Stan Licznika Export` | Total meter reading (production) |

### Metadata Sensors
| Sensor Name | Description |
|-------------|-------------|
| `Adres` | Installation address |
| `Taryfa` | Tariff type (e.g., G11, G12, G12w) |
| `PPE` | PPE identification number |
| `Numer Licznika` | Meter serial number |
| `Data Aktywacji` | Mój Licznik app activation date* |

*Only available for prosumer accounts

### Diagnostic / Price Sensors

These sensors show the **currently configured prices** — visible under the "Diagnostic" section of the device page:

| Sensor Name | Description | Unit | Tariff |
|-------------|-------------|------|--------|
| `Cena Poboru` | Import price (single-zone) | PLN/kWh | G11 only |
| `Cena Poboru Strefa 1` | Peak zone import price | PLN/kWh | G12/G12w only |
| `Cena Poboru Strefa 2` | Off-peak zone import price | PLN/kWh | G12/G12w only |
| `Cena Oddania` | Export compensation rate | PLN/kWh | Prosumer only* |
| `Współczynnik Prosumencki` | Net billing coefficient | — | Prosumer only* |

\* Only created for accounts with export metering (prosumer/producer-consumer)

> [!TIP]
> You can use `Cena Poboru` (G11) or `Cena Poboru Strefa 1/2` (G12/G12w) as **"Use entity with current price"** in the Energy Dashboard configuration — this lets you update the price without re-configuring the dashboard.

### Prosumer Sensors (auto-created for prosumer accounts)
| Sensor Name | Description |
|-------------|-------------|
| `Bilans Prosumencki` | Net billing balance (export × coeff − import) in kWh |

---

## 📊 Energy Dashboard Setup

To see correctly calculated statistics **and costs** in the Energy Dashboard, you MUST select the specific sensors labeled **"Panel Energia"**.

Go to **Settings** → **Dashboards** → **Energy** → **Electricity grid** section.

### Step 1: Add Grid Consumption

Click **"Add consumption"** (Dodaj zużycie) for each zone:

**Single-Zone (G11):** Add `Panel Energia Zużycie`
**Multi-Zone (G12/G12w):** Add `Panel Energia Strefa 1` and `Panel Energia Strefa 2` separately

For each consumption entry, configure **cost tracking** (Śledzenie kosztów):
1. Select **"Use entity with current price"** (Użyj encji z bieżącą ceną)
2. In the **"Entity with current price"** field, choose the matching **Cena Poboru** sensor:
   - G11: `Cena Poboru`
   - G12/G12w zone 1: `Cena Poboru Strefa 1`
   - G12/G12w zone 2: `Cena Poboru Strefa 2`

### Step 2: Add Return to Grid

Click **"Add return"** (Dodaj produkcję) for each zone:

**Single-Zone (G11):** Add `Panel Energia Produkcja`
**Multi-Zone (G12/G12w):** Add `Panel Energia Produkcja Strefa 1` and `Produkcja Strefa 2` separately

For each return entry, configure **compensation tracking** (Rekompensata za eksport):
1. Select **"Use entity tracking total compensation"** (Użyj encji śledzącej całkowitą wartość rekompensaty)
2. In the **"Entity with total compensation"** field, choose the matching **Rekompensata** sensor:
   - G11: `Panel Energia Produkcja Rekompensata`
   - G12/G12w zone 1: `Panel Energia Produkcja Strefa 1 Rekompensata`
   - G12/G12w zone 2: `Panel Energia Produkcja Strefa 2 Rekompensata`

### Step 3: Power Measurement

Select **"No power sensor"** (Brak sensora mocy) — this integration provides energy data only, not real-time power.

Click **Save** (Zapisz).

> [!WARNING]
> After saving, the Energy Dashboard may show **"Encja niezdefiniowana"** (Undefined entity) for some sensors. **This is expected.** Panel Energia sensors are statistics-only entities that don't have a live state — their data will appear correctly in the dashboard charts after the next data update cycle (typically within 1 hour).

> [!IMPORTANT]
> **Do NOT use** `Zużycie Dziś`, `Produkcja Dziś`, or `Stan Licznika` sensors for the Energy Dashboard — only **Panel Energia** sensors produce correct cumulative statistics.

> [!NOTE]
> **Why different cost methods for import vs export?** Import costs use a **price entity** (PLN/kWh) — HA multiplies it by hourly consumption automatically. Export compensation uses a **total compensation entity** (PLN) — the integration pre-calculates the cumulative amount based on the configured export rate and prosumer coefficient.

---

## 📅 History Import & Repair

Use this feature if you have missing data OR if you see incorrect spikes in your Energy Dashboard.

1.  Go to **Settings** → **Devices & Services** → **Energa My Meter** → **Configure**.
2.  Select **"Download History"**.
3.  Choose a **Start Date** (e.g., 30 days ago, or your contract date shown in the dialog).
4.  Click **Submit**.

**How it works:** The integration downloads fresh data from Energa and calculates clean, continuous statistics based on your current meter reading. This effectively **overwrites** any corrupted historical data, including cost data.

*The process happens in the background. Check logs for progress.*

> [!TIP]
> If you need a completely clean slate (e.g., after a tariff change or major data corruption), first use **"Clear Energy Panel Statistics"** from the Configure menu, then run **"Download History"**.

---

## ⚠️ Limitations

- **Supported Tariffs:** G11 (single-zone) and two-zone tariffs (G12, G12w, G12r) are fully supported. Three-zone tariffs (G13) are not supported — if you need G13, please [open an issue](https://github.com/ergo5/hass-energa-my-meter-api/issues).
- **PLN Currency:** Cost calculation is in Polish złoty (PLN) only.
- **Statistics Sensors:** Panel Energia sensors show as "unknown" or "unavailable" in entity lists (this is normal — they work in Energy Dashboard).
- **Hourly Granularity:** Statistics are hourly — no sub-hour precision.

---

## 🐛 Troubleshooting

### Persistent errors in logs?

If you see repeated **errors** (not warnings) related to Energa, try removing and re-adding the integration:
1. Go to **Settings** → **Devices & Services** → **Energa My Meter**
2. Click the **3 dots** → **Delete**
3. Add the integration again with your credentials

### Sensors "Panel Energia" Missing?

- Panel Energia sensors are created during integration setup and appear in the entity list
- They show as **"unknown"** — this is expected, their data lives in the statistics database
- If missing entirely, check that your Energa account has active meters with consumption data

### Cost Not Showing in Energy Dashboard?

1. **Verify prices are configured:** Settings → Energa My Meter → Configure → Set Energy Prices
2. **Check price sensors work:** Verify that `Cena Poboru Strefa 1/2` shows a numeric value (not "unavailable") in the entity list
3. **Verify Dashboard config:** Import must use **"Use entity with current price"** + `Cena Poboru`. Export must use **"Use entity tracking total compensation"** + `Rekompensata`
4. **Check statistics exist:** Look for **Rekompensata** statistics in Developer Tools → Statistics
5. **After changing prices:** Use **"Download History"** to recalculate cost statistics with the new rates

### Data Not Appearing in Energy Dashboard?

Ensure you selected the correct **Panel Energia** sensors, not the "Daily" or "State" sensors. See [Energy Dashboard Setup](#-energy-dashboard-setup) above.

### About "Data Aktywacji" Sensor

This sensor shows the **activation date of the Mój Licznik mobile app**, not the contract signing date. It's only available for prosumer (producer-consumer) accounts and may not appear for regular consumer accounts.

---

## 📄 Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

### Disclaimer
This is a custom integration and is not affiliated with Energa Operator. Use at your own risk.
