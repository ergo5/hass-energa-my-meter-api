# Energa Mobile Integration for Home Assistant

![Energa Mobile API Logo](logo.png)


![Version](https://img.shields.io/badge/version-v4.0.2-green)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A robust integration for **Energa Operator** in Home Assistant. It downloads data from the "Mój Licznik" service (Energa Operator) and integrates seamlessly with the **Energy Dashboard**. Features **self-healing history import** and correct cumulative statistics.

---

## ✨ Key Features

*   **📊 Energy Dashboard Ready:** Dedicated sensors (`Panel Energia`) designed specifically for correct statistics.
*   **🛡️ Anchor-Based Statistics:** Calculates history backwards from the current meter reading to guarantee perfect data continuity.
*   **⚡ Hourly Granularity:** Precise hourly consumption/production tracking.
*   **🛠️ Auto-Repair (Self-Healing):** The "Download History" feature automatically fixes gaps and corrupted data.
*   **🔍 OBIS Auto-Detect:** Automatically identifies usage (1.8.0) and production (2.8.0).

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

## 📊 Energy Dashboard Setup (Konfiguracja Panelu Energia)

To see correctly calculated statistics in the Energy Dashboard, you MUST select the specific sensors labeled with **"(Panel Energia)"**.

| Dashboard Section | Correct Sensor Name | Description |
| :--- | :--- | :--- |
| **Grid Consumption** (Pobór z sieci) | **Energa [Twój ID] Panel Energia Zużycie** | Specially configured for HA Statistics. Do not confuse with "Daily". |
| **Return to Grid** (Oddawanie do sieci) | **Energa [Twój ID] Panel Energia Produkcja** | Specially configured for HA Statistics. |

> [!TIP]
> Do NOT use `Energa Pobór Dziś` or `Stan Licznika` for the Energy Dashboard. Only use the ones marked **(Panel Energia)**.

> [!NOTE]
> **"Entity Unavailable" (Encja niedostępna)?**
> This is **NORMAL** and expected. The statistics sensors (`energa_import_stats`, `energa_export_stats`) are designed *only* for the Energy Dashboard background processing. They do not have a live "state" to display in the standard UI, so Home Assistant may show them as "Unavailable" or "Unknown" in lists. **They will still work correctly in the Energy Dashboard.**

---

## 📅 History Import & Repair (Naprawa Historii)

Use this feature if you have missing data OR if you see incorrect spikes in your Energy Dashboard.

1.  Go to **Settings** -> **Devices & Services** -> **Energa Mobile** -> **Configure**.
2.  Select **"Pobierz Historię Danych"**.
3.  Choose a **Start Date** (e.g., 30 days ago).
4.  Click **Submit**.

**How it works:** The integration will download fresh data from Energa and calculate clean, continuous statistics based on your current meter reading. This effectively **overwrites** any corrupted historical data in Home Assistant.

*The process happens in the background. Check logs for progress.*

---

## 🐛 Troubleshooting

*   **Sensors "Panel Energia" missing?** Check the **Diagnostic** entities section or enable "Show disabled entities".
*   **Data Not Appearing?** Ensure you selected the correct `(Panel Energia)` sensors in the Dashboard.

### Disclaimer
This is a custom integration and is not affiliated with Energa Operator. Use at your own risk.
