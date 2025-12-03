<div align="center">
  <img src="https://raw.githubusercontent.com/ergo5/hass-energa-my-meter-api/main/logo.png" alt="Energa API Logo" width="200"/>
</div>

# Energa Mobile API for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A modern custom integration for **Energa Operator** meters in Home Assistant.

This component is built from the ground up to utilize the native **Mobile API** (`api-mojlicznik`), providing a robust and stable connection for retrieving energy data. It emulates the behavior of the official iOS application to ensure reliable communication with Energa servers.

---

## ✨ Key Features

* **Mobile API Protocol:** Connects directly to the `api-mojlicznik` endpoint for improved stability.
* **Secure Authentication:** The integration generates a unique, local device token during installation. It does not rely on your personal phone's ID, ensuring your official mobile app remains logged in and secure.
* **Metadata & Diagnostics:** Retrieves tariff, address, and contract details.
* **Device Support:** Groups all entities under a single "Energa Meter" device.
* **Energy Dashboard Ready:** Sensors use the `total_increasing` state class.

---

## 📦 Installation

### Option 1: HACS (Recommended)

1.  Open **HACS** in Home Assistant.
2.  Go to the **Integrations** section.
3.  Click the menu (three dots) in the top-right corner and select **Custom repositories**.
4.  Paste the URL of this repository.
5.  Select **Integration** as the category.
6.  Click **Add** and then download the integration.
7.  **Restart Home Assistant**.

### Option 2: Manual Installation

1.  Download the `energa_mobile` folder from this repository.
2.  Copy it into the `custom_components` directory in your Home Assistant configuration folder (e.g., `/config/custom_components/energa_mobile`).
3.  Restart Home Assistant.

---

## ⚙️ Configuration

Configuration is handled entirely via the Home Assistant UI.

1.  Go to **Settings** -> **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for **Energa Mobile API**.
4.  Enter your **Energa Mój Licznik** username (email) and password.

The integration will automatically authenticate, generate a secure device token, and discover your meters.

---

## 📊 Entities

The integration creates a Device representing your meter with the following entities:

| Entity | Type | Description |
| :--- | :--- | :--- |
| **Energa Import** | Sensor | Total energy consumed from the grid (Zone A+). |
| **Energa Export** | Sensor | Total energy returned to the grid (Zone A-). |
| **Tariff** | Diagnostic | Current tariff plan (e.g., G11, G12). |
| **PPE Address** | Diagnostic | Physical address of the installation. |
| **Seller** | Diagnostic | Name of the energy seller. |
| **Contract Date** | Diagnostic | Start date of the contract. |
| **Meter Number** | Diagnostic | PPE identification number. |

---

## 🔄 Migrating and Preserving History (The Final Protocol)

If you are switching from a previous Energa integration and wish to keep your long-term statistics (Energy Dashboard history), you must perform an Entity ID swap. **This process requires the removal of the old integration to prevent ID conflicts.**

### Step 1: Eliminate the Old Integration (Mandatory Cleanup)

1.  **Remove Old Integration:** Navigate to **Settings** → **Devices & Services** → **Integrations**. Find the old "Energa" integration (the one based on web scraping) and select **Delete** to remove it completely.
2.  **Restart Home Assistant:** Perform a full restart (**Settings** → **System** → **Restart**). This clears the registry cache and flags the old Entity IDs as disposable.

### Step 2: Purge the Ghost ID and Swap

1.  **Verify ID Status:** Go to **Developer Tools** → **Entities**. Search for the old historical ID (e.g., `sensor.energa_my_meter_30132815_consumed_strefa_calodobowa`).
2.  **Purge Ghost:** If the old entity ID still appears (even if marked as 'Removed' or 'Unavailable'), click it and scroll to the bottom to click **REMOVE** (Delete from Registry). This action frees the name permanently.
3.  **Rename New Entities:** Find the **new** working sensors (e.g., `sensor.energa_mobile_pobor_import`).
4.  Change the **Entity ID** of the new sensor to match the **exact historical ID** you just freed.

After this process, Home Assistant will seamlessly link the historical data to your new, stable sensor.

---

## 🐛 Troubleshooting

If you encounter issues, please enable debug logging to provide more details:

```yaml
logger:
  default: info
  logs:
    custom_components.energa_mobile: debug
