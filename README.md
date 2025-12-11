<div align="center">
  <img src="images/logo.png" alt="Energa Mobile API Logo" width="300"/>
</div>

# Energa Mobile API (OBIS Auto-Detect) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration) [![version](https://img.shields.io/badge/version-v2.7.7-green)](https://github.com/ergo5/hass-energa-my-meter-api/releases)

A robust, native integration for **Energa Operator** meters in Home Assistant.

This integration uses the official **Mobile API** (`api-mojlicznik`) to provide reliable energy data without parsing HTML. It features **Dynamic OBIS Auto-Detection** to correctly identify Import/Export registers (solving missing PV production issues) and includes a powerful **History Importer** to backfill your Energy Dashboard with past data.

---

## ✨ Key Features (v2.7+)

* **📊 Historic Data Import (New!):** Easily backfill your Energy Dashboard with data from previous months or years directly from the integration configuration menu.
* **🛡️ Anti-Ban Protection:** The history importer includes a "safety brake" (1.5s delay per day) to prevent Energa's API from blocking your IP address during large downloads.
* **🔄 Auto-Retry & Self-Healing:** If the API is unavailable, the integration automatically pauses and retries with an increasing backoff interval (2m → 5m → 15m), preventing permanent failures.
* **⚡ True Hourly Data:** Consumption is calculated from **hourly charts**, ensuring your Energy Dashboard bars update every hour with precise granularity, unlike standard total counters that update only once a day.
* **🔍 OBIS Auto-Detect:** Automatically scans meter metadata to find the correct codes for **Import (1.8.0)** and **Export (2.8.0)**.
* **🔐 Secure Auth:** Uses mobile token authentication with a Cookie fallback mechanism. Zero CAPTCHA issues.

---

## 📦 Installation

### Option 1: HACS (Recommended)

1.  Open **HACS** in Home Assistant.
2.  Go to **Integrations** > **Custom repositories**.
3.  Add this repository URL: `https://github.com/ergo5/hass-energa-my-meter-api`
4.  Select **Integration** type.
5.  Install **Energa Mobile**.
6.  **Restart Home Assistant**.

### Option 2: Manual

1.  Download the `energa_mobile` folder from the latest release.
2.  Copy it to your `custom_components` directory (e.g., `/config/custom_components/energa_mobile`).
3.  Restart Home Assistant.

---

## ⚙️ Configuration

1.  Go to **Settings** -> **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for **Energa Mobile (OBIS Auto-Detect)**.
4.  Enter your **Energa Mój Licznik** username (email) and password.

---

## 📊 Entities & Energy Dashboard

The integration creates specific sensors for different purposes.

### ⚡ For Energy Dashboard (Use These!)

These sensors are calculated from **hourly charts**. They reset to 0 at midnight.
* **Grid Consumption:** `sensor.energa_pobor_dzis` (Energa Pobór Dziś)
* **Return to Grid:** `sensor.energa_produkcja_dzis` (Energa Produkcja Dziś)

> **Configuration:**
> Go to **Dashboards** -> **Energy**.
> * Under *Grid Consumption*, add `sensor.energa_pobor_dzis`.
> * Under *Return to Grid*, add `sensor.energa_produkcja_dzis`.

### ℹ️ Informational (Total Counters)

These sensors show the raw state of the meter (Index/Total).
* **Note:** Energa typically updates these values **only once every 24h**. Do **NOT** use them for the Energy Dashboard, or you will get a single giant bar once a day.
* `sensor.energa_stan_licznika_pobor` (Total Import)
* `sensor.energa_stan_licznika_produkcja` (Total Export)

---

## 📅 How to Import History (Backfill)

You can download historical data (e.g., from the beginning of your contract) to populate the Home Assistant Energy Dashboard.

1.  Go to **Settings** -> **Devices & Services**.
2.  Find **Energa Mobile** and click **Configure**.
3.  Select **"Pobierz Historię" (Download History)**.
4.  Select the **Start Date** (e.g., your contract start date or the beginning of the year).
5.  Click **Submit**.

**⚠️ Important Notes:**
* **Background Process:** The download runs in the background. You can continue using HA.
* **Safety Delay:** To avoid getting banned by Energa, the process waits **1.5 seconds** between each downloaded day. Importing 1 year of data takes about **10 minutes**.
* **Visualization:** Data will appear in the Energy Dashboard after Home Assistant processes the statistics (usually within 15-60 minutes).

---

## 🐛 Troubleshooting

**"Invalid Source" error in logs:**
This is fixed in v2.7.6+. The integration now correctly identifies existing sensors in the registry.

**Integration shows "Unavailable":**
This usually means the Energa API is down or rate-limiting is active. The integration will automatically retry in 2, 5, or 15 minutes. **Do not reload manually**, just wait.

**Debug Logging:**
If you encounter issues, enable debug logging to see exactly what's happening:
1.  Go to the Integration tile.
2.  Click "Enable debug logging".
3.  Wait for the issue to recur or perform an action.
4.  Disable debug logging to download the log file.

---

**Disclaimer:** This is a custom integration and is not affiliated with Energa Operator. Use at your own risk.