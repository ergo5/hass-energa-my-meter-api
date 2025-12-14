<div align="center">
  <img src="/logo.png" alt="Energa Mobile API Logo" width="300"/>
</div>

<h1 align="center">Energa Mobile Integration for Home Assistant</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Badge"></a>
  <img src="https://img.shields.io/badge/version-v3.5.20-blue" alt="Version Badge">
</p>

<p align="center">
  A robust integration for <strong>Energa Operator</strong> in Home Assistant. It downloads data from the "Mój Licznik" service (Energa Operator) and integrates seamlessly with the **Energy Dashboard**.
  Features **stable history import** and database resilience.
</p>

---

<h2 id="key-features">✨ Key Features</h2>

<ul>
    <li><strong>📊 Energy Dashboard Ready:</strong> Dedicated sensors with clear names (`(Panel Energia)`) designed specifically for correct statistics.</li>
    <li><strong>🛡️ Database Resilience:</strong> Uses unique entity IDs to preventing history corruption.</li>
    <li><strong>⚡ Hourly Granularity:</strong> Calculates consumption from hourly charts for precise tracking.</li>
    <li><strong>🔍 OBIS Auto-Detect:</strong> Automatically identifies Import (1.8.0) and Export (2.8.0) registers.</li>
    <li><strong>📈 History Backfill:</strong> Allows importing historical data (up to 30-60 days) to fill gaps in the Energy Dashboard without creating data spikes.</li>
</ul>

---

<h2 id="installation">📦 Installation</h2>

<h3>Option 1: HACS (Recommended)</h3>
<ol>
    <li>Open <strong>HACS</strong> -> <strong>Integrations</strong> -> <strong>Custom repositories</strong>.</li>
    <li>Add URL: <code>https://github.com/ergo5/hass-energa-my-meter-api</code></li>
    <li>Category: <strong>Integration</strong>.</li>
    <li>Install <strong>Energa Mobile Integration</strong> and restart Home Assistant.</li>
</ol>

<h3>Option 2: Manual</h3>
<ol>
    <li>Download <code>energa_mobile</code> folder from the release.</li>
    <li>Copy to <code>/config/custom_components</code>.</li>
    <li>Restart Home Assistant.</li>
</ol>

<h3>Configuration</h3>
<ol>
    <li>Go to <strong>Settings</strong> -> <strong>Devices & Services</strong>.</li>
    <li>Add Integration -> Search for <strong>Energa Mobile</strong>.</li>
    <li>Login With your <strong>Energa Mój Licznik</strong> credentials.</li>
</ol>

---

<h2 id="energy-dashboard">📊 Energy Dashboard Setup (Konfiguracja Panelu Energia)</h2>

<p>To see correctly calculated statistics in the Energy Dashboard, you MUST select the specific sensors labeled with <strong>"(Panel Energia)"</strong>. These are separate from the daily counters.</p>

<table>
    <thead>
        <tr>
            <th>Dashboard Section</th>
            <th>Correct Sensor Name</th>
            <th>Description</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>Grid Consumption</strong> (Pobór z sieci)</td>
            <td><strong>Energa Import (Panel Energia)</strong></td>
            <td>Specially configured for HA Statistics. Do not confuse with "Daily".</td>
        </tr>
        <tr>
            <td><strong>Return to Grid</strong> (Oddawanie do sieci)</td>
            <td><strong>Energa Export (Panel Energia)</strong></td>
            <td>Specially configured for HA Statistics.</td>
        </tr>
    </tbody>
</table>

> [!TIP]
> Do NOT use `Energa Pobór Dziś` or `Stan Licznika` for the Energy Dashboard. Only use the ones marked **(Panel Energia)**.

---

<h2 id="import-history">📅 History Import (Backfill)</h2>

<p>If you want to view past data (from before you installed the integration):</p>

<ol>
    <li>Go to <strong>Settings</strong> -> <strong>Devices & Services</strong> -> <strong>Energa Mobile</strong> -> <strong>Configure</strong>.</li>
    <li>Select **"Pobierz Historię" (Download History)**.</li>
    <li>Choose a **Start Date** (e.g., 30 days ago).</li>
    <li>Click **Submit**.</li>
</ol>

<p><em>The process happens in the background. Data will appear in the Energy Dashboard after Home Assistant processes the statistics (usually 15-60 minutes).</em></p>

---

<h2 id="troubleshooting">🐛 Troubleshooting</h2>

<ul>
    <li><strong>Sensors "Panel Energia" missing?</strong> Check the **Diagnostic** section of your device in Home Assistant (Settings -> Devices -> Energa). They might be grouped there to keep the main view clean.</li>
    <li><strong>Data Not Appearing?</strong> Ensure you selected the correct `(Panel Energia)` sensors in the Dashboard.</li>
</ul>

<h3>Disclaimer</h3>
<p>This is a custom integration and is not affiliated with Energa Operator. Use at your own risk.</p>

---

<h2 id="fixing-spikes">🛠️ Fixing Data Spikes (Cleaning Old Statistics)</h2>

<p>If you are upgrading from an older version and see a massive data spike (e.g., 25,000 kWh in one hour), follow these steps to reset the statistics before running a new import:</p>

<ol>
    <li>Go to <strong>Developer Tools</strong> -> <strong>Statistics</strong>.</li>
    <li>Search for <code>Energa Import (Panel Energia)</code>.</li>
    <li>Click the <strong>Fix Issue</strong> icon (if present) or finding the entity in the list.</li>
    <li>Click the <strong>trash bin icon</strong> (Clear) next to the entity to remove corrupted statistics.</li>
    <li>Repeat for <code>Energa Export (Panel Energia)</code>.</li>
    <li>After clearing, go to the integration configuration and run <strong>Download History</strong> again. The new Smart Import will fill the gap correctly.</li>
</ol>
