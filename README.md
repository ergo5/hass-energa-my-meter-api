<div align="center">
  <img src="https://raw.githubusercontent.com/ergo5/hass-energa-my-meter-api/main/logo.png" alt="Energa API Logo" width="200"/>
</div>

# Energa Mobile API (Hybrid Edition) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A robust custom integration for **Energa Operator** meters in Home Assistant, built for stability and precision.

This component utilizes a unique **Hybrid Engine**: it uses the modern **Mobile API** protocol (`api-mojlicznik`) for secure, token-based authentication (bypassing CAPTCHA issues), while leveraging the legacy chart data logic to retrieve accurate, **hourly energy consumption** details directly from Energa's graph data.

---

## ✨ Key Features

* **Hybrid Engine (New!):** Combines the security of the Mobile App login with the data precision of web charts.
* **True Hourly Data:** Unlike standard API readings which may update only once a day, this integration calculates usage from the **hourly charts**, ensuring your Energy Dashboard bars update every hour.
* **Secure Authentication:** Generates a unique, local device token. Does not rely on your personal phone's ID, keeping your official app secure.
* **Metadata & Diagnostics:** Retrieves tariff, address, and contract details.
* **Energy Dashboard Ready:** "Today" sensors use `total_increasing` class for perfect integration with Home Assistant's Energy panel.

---

## 📦 Installation

### Option 1: HACS (Recommended)

1.  Open **HACS** in Home Assistant.
2.  Go to the **Integrations** section.
3.  Click the menu (three dots) in the top-right corner and select **Custom repositories**.
4.  Paste the URL of this repository:
    ```text
    [https://github.com/ergo5/hass-energa-my-meter-api](https://github.com/ergo5/hass-energa-my-meter-api)
    ```
5.  Select **Integration** as the category.
6.  Click **Add** and then download the integration.
7.  **Restart Home Assistant**.

### Option 2: Manual Installation

1.  Download the `energa_mobile` folder from this repository.
2.  Copy it into the `custom_components` directory in your Home Assistant configuration folder (e.g., `/config/custom_components/energa_mobile`).
3.  Restart Home Assistant.

---

## ⚙️ Configuration

Configuration is handled entirely via the Home Assistant UI.

1.  Go to **Settings** -> **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for **Energa Mobile API**.
4.  Enter your **Energa Mój Licznik** username (email) and password.

The integration will automatically authenticate, generate a secure device token, and discover your meters.

---

## 📊 Entities

The integration creates a Device representing your meter with the following entities.

### ⚡ Primary Sensors (For Energy Dashboard)

These sensors are calculated from hourly charts and update frequently throughout the day. **Use these for your Energy Dashboard.**

| Entity | Type | Description |
| :--- | :--- | :--- |
| **Energa Pobór Dziś** (`daily_pobor`) | Sensor | Sum of hourly consumption for the current day. Resets at midnight. |
| **Energa Produkcja Dziś** (`daily_produkcja`) | Sensor | Sum of hourly production for the current day. Resets at midnight. |

### ℹ️ Informational Sensors (Total Counters)

These sensors show the raw state of the meter (Last Measurement). Note: Energa often updates these only once every 24h.

| Entity | Type | Description |
| :--- | :--- | :--- |
| **Energa Import Total** (`pobor`) | Sensor | Total lifetime consumption. |
| **Energa Export Total** (`produkcja`) | Sensor | Total lifetime production. |

### 🛠️ Diagnostics

| Entity | Type | Description |
| :--- | :--- | :--- |
| **Tariff** | Diagnostic | Current tariff plan (e.g., G11, G12). |
| **PPE Address** | Diagnostic | Physical address of the installation. |
| **Seller** | Diagnostic | Name of the energy seller. |
| **Contract Date** | Diagnostic | Start date of the contract. |
| **Meter Number** | Diagnostic | PPE identification number. |

---

## ⚡ Energy Dashboard Configuration

To get beautiful hourly bars in your Energy Dashboard, follow this setup:

1.  Go to **Settings** -> **Dashboards** -> **Energy**.
2.  **Grid Consumption:** Add source -> Select **`Energa Pobór Dziś`**.
3.  **Return to Grid:** Add source -> Select **`Energa Produkcja Dziś`**.

*Do not use the "Total" sensors for the dashboard, as they may result in a single large bar once a day.*

---

## 🔄 Migrating and Preserving History

If you are switching from a previous Energa integration and wish to keep your long-term statistics (Energy Dashboard history), you must perform an Entity ID swap.

**The Protocol:**

1.  **Remove Old Integration:** Delete the old integration from **Devices & Services**.
2.  **Restart HA:** Essential to clear the registry.
3.  **Purge Ghost IDs:** Go to **Developer Tools** -> **Entities**. Search for your old sensor ID (e.g., `sensor.energa_my_meter_..._consumed`). If it still exists (unavailable), click it -> **Delete**.
4.  **Rename New Sensors:**
    * Find the new **`Energa Pobór Dziś`** sensor.
    * Rename its **Entity ID** to match your **old historical ID** exactly.
    * *(Repeat for the Production sensor).*

After this, Home Assistant will treat the new hybrid sensor as the continuation of your old history.

---

## 🐛 Troubleshooting

If you encounter issues, please enable debug logging to provide more details:

```yaml
logger:
  default: info
  logs:
    custom_components.energa_mobile: debug
