<div align="center">
  <img src="/logo.png" alt="Energa Mobile API Logo" width="300"/>
</div>

<h1 align="center">Energa Mobile Integration for Home Assistant</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Badge"></a>
  <img src="https://img.shields.io/badge/version-v4.0.2-green" alt="Version Badge">
</p>

<p align="center">
  A robust integration for <strong>Energa Operator</strong> in Home Assistant. It downloads data from the "Mój Licznik" service (Energa Operator) and integrates seamlessly with the **Energy Dashboard**.
  Features **self-healing history import** and correct cumulative statistics.
</p>

---

<h2 id="key-features">✨ Key Features</h2>

<ul>
    <li><strong>📊 Energy Dashboard Ready:</strong> Dedicated sensors (`Panel Energia`) designed specifically for correct statistics.</li>
    <li><strong>🛡️ Anchor-Based Statistics:</strong> Calculates history backwards from the current meter reading to guarantee perfect data continuity.</li>
    <li><strong>⚡ Hourly Granularity:</strong> Precise hourly consumption/production tracking.</li>
    <li><strong>🛠️ Auto-Repair (Self-Healing):</strong> The "Download History" feature automatically fixes gaps and corrupted data.</li>
    <li><strong>🔍 OBIS Auto-Detect:</strong> automatically identifies usage (1.8.0) and production (2.8.0).</li>
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

<h3>Configuration</h3>
<ol>
    <li>Go to <strong>Settings</strong> -> <strong>Devices & Services</strong>.</li>
    <li>Add Integration -> Search for <strong>Energa Mobile</strong>.</li>
    <li>Login With your <strong>Energa Mój Licznik</strong> credentials.</li>
</ol>

---

<h2 id="energy-dashboard">📊 Energy Dashboard Setup (Konfiguracja Panelu Energia)</h2>

<p>To see correctly calculated statistics in the Energy Dashboard, you MUST select the specific sensors labeled with <strong>"(Panel Energia)"</strong>.</p>

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

<h2 id="import-history">📅 History Import & Repair (Naprawa Historii)</h2>

<p>Use this feature if you have missing data OR if you see incorrect spikes in your Energy Dashboard.</p>

<ol>
    <li>Go to <strong>Settings</strong> -> <strong>Devices & Services</strong> -> <strong>Energa Mobile</strong> -> <strong>Configure</strong>.</li>
    <li>Select **"Pobierz Historię Danych"**.</li>
    <li>Choose a **Start Date** (e.g., 30 days ago).</li>
    <li>Click **Submit**.</li>
</ol>

<p><strong>How it works:</strong> The integration will download fresh data from Energa and calculate clean, continuous statistics based on your current meter reading. This effectively <strong>overwrites</strong> any corrupted historical data in Home Assistant.</p>

<p><em>The process happens in the background. Check logs for progress.</em></p>

---

<h2 id="troubleshooting">🐛 Troubleshooting</h2>

<ul>
    <li><strong>Sensors "Panel Energia" missing?</strong> Check the **Diagnostic** entities section or enable "Show disabled entities".</li>
    <li><strong>Data Not Appearing?</strong> Ensure you selected the correct `(Panel Energia)` sensors in the Dashboard.</li>
</ul>

<h3>Disclaimer</h3>
<p>This is a custom integration and is not affiliated with Energa Operator. Use at your own risk.</p>
