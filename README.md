<div align="center">
  <img src="/logo.png" alt="Energa API Logo" width="300"/>
</div>

# Energa Mobile API (OBIS Auto-Detect) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration) [![version](https://img.shields.io/github/v/release/ergo5/hass-energa-my-meter-api)](https://github.com/ergo5/hass-energa-my-meter-api/releases)

A robust, native integration for **Energa Operator** meters in Home Assistant.

This is the **v2.0+** rewrite of the integration. It utilizes the official **Mobile API** (`api-mojlicznik`) and features a **Dynamic OBIS Auto-Detection Engine**. This engine correctly identifies Import and Export registers directly from your meter's metadata, effectively resolving common issues with missing Production (PV) data.

---

## ✨ Key Features

* **OBIS Auto-Detect:** Automatically scans meter objects to find correct codes for **Import (1.8.0)** and **Export (2.8.0)**. No manual configuration required.
* **True Hourly Data:** Consumption is calculated directly from Energa's **hourly charts**. This ensures your **Energy Dashboard** bars update every hour with precise granularity.
* **Robust Authentication:** Uses a secure mobile token flow with a Cookie fallback mechanism. Zero CAPTCHA issues.
* **Energy Dashboard Ready:** "Today" sensors use the `total_increasing` state class, handling daily resets perfectly for Home Assistant's Energy panel.
* **Plug & Play:** Just enter your Username and Password.

---

## 📦 Installation

### Option 1: HACS (Recommended)

1.  Open **HACS** in Home Assistant.
2.  Go to the **Integrations** section.
3.  Click the menu (three dots) in the top-right corner and select **Custom repositories**.
4.  Paste the URL of this repository.
    ```text
    https://github.com/ergo5/hass-energa-my-meter-api
    ```
5.  Select **Integration** as the category and click **Add**.
6.  Download the integration and **Restart Home Assistant**.

### Option 2: Manual Installation

1.  Download the `energa_mobile` folder from this repository.
2.  Copy it into the `custom_components` directory in your Home Assistant configuration folder (e.g., `/config/custom_components/energa_mobile`).
3.  Restart Home Assistant.

---

## ⚙️ Configuration

1.  Go to **Settings** -> **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for **Energa Mobile (OBIS Auto-Detect)**.
4.  Enter your **Energa Mój Licznik** username (email) and password.

---

## 📊 Entities

The integration creates a Device representing your meter with the following entities.

### ⚡ Primary Sensors (For Energy Dashboard)

These sensors are calculated from **hourly charts** and reset to 0 at midnight.

| Entity Name | Generated ID (Example) | Description |
| :--- | :--- | :--- |
| **Energa Pobór Dziś** | `sensor.energa_pobor_dzis` | Sum of hourly consumption for the current day. |
| **Energa Produkcja Dziś** | `sensor.energa_produkcja_dzis` | Sum of hourly production (PV) for the current day. |

### ℹ️ Informational Sensors (Total Counters)

These sensors show the raw state of the meter (Last Measurement).
*> **Note:** Energa typically updates these values only **once every 24h** (e.g., at 4:00 AM). Do NOT use these for the Energy Dashboard.*

| Entity Name (PL) | Generated ID (Example) | Description |
| :--- | :--- | :--- |
| **Energa Stan Licznika (Pobór)** | `sensor.energa_stan_licznika_pobor` | Total lifetime consumption (OBIS 1.8.0). |
| **Energa Stan Licznika (Produkcja)** | `sensor.energa_stan_licznika_produkcja` | Total lifetime production (OBIS 2.8.0). |

### 🛠️ Diagnostics

| Entity | Description |
| :--- | :--- |
| **Taryfa** | Current tariff plan (e.g., G11, G12). |
| **Adres** | Physical address of the installation. |
| **PPE** | Point of Power Consumption (PPE) number. |

---

## ⚡ Energy Dashboard Configuration

To get beautiful hourly bars in your Energy Dashboard, you **must use the "Dziś" (Today) sensors**, not the "Stan Licznika" sensors.

1.  Go to **Settings** -> **Dashboards** -> **Energy**.
2.  **Grid Consumption:** Add source -> Select **`Energa Pobór (Dziś)`**.
3.  **Return to Grid:** Add source -> Select **`Energa Produkcja (Dziś)`**.

**Why?** Since Energa updates the "Total" counter only once a day, using it would result in erroneous data display (flat line all day + huge spike at night). The "Today" sensors are built from charts provided by Energa with hourly resolution.

---

## 🔄 Migration & History Preservation

If you are switching from an older version of this (or another) Energa integration and want to keep your long-term statistics:

1.  **Note down** the Entity IDs of your old sensors.
2.  **Delete** the old integration from the *Devices & Services* page.
3.  **Restart** Home Assistant.
4.  **Install** and configure this new version.
5.  Go to **Settings** -> **Entities**.
6.  Find the new entity (e.g., `sensor.energa_pobor_dzis`).
7.  Click on it -> **Settings (cog wheel)** -> Change the **Entity ID** to match your old sensor's ID exactly.
8.  Home Assistant will ask if you want to merge history. Confirm.

---

## 🐛 Troubleshooting

If you encounter issues (e.g., missing production data), please enable debug logging to check which OBIS codes are being detected by the engine:

```yaml
logger:
  default: info
  logs:
    custom_components.energa_mobile: debug
