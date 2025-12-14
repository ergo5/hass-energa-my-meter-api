<div align="center">
  <img src="/logo.png" alt="Energa Mobile API Logo" width="300"/>
</div>

<h1 align="center">Energa Mobile Integration for Home Assistant</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Badge"></a>
  <img src="https://img.shields.io/badge/version-v3.5.13-blue" alt="Version Badge">
</p>

<p align="center">
  A robust integration for <strong>Energa Operator</strong> in Home Assistant. It downloads data from the "Mój Licznik" service (Energa Operator) and integrates seamlessly with the **Energy Dashboard**.
  Features **stable history import** and database resilience.
</p>

---

<h2 id="key-features">✨ Key Features</h2>

<ul>
    <li><strong>📊 Energy Dashboard Ready:</strong> Dedicated sensors (<code>import_total</code>, <code>export_total</code>) designed specifically for correct statistics in Home Assistant.</li>
    <li><strong>🛡️ Database Resilience:</strong> Uses unique entity IDs to prevent history corruption.</li>
    <li><strong>🔄 Restart Proof:</strong> Maintains last known energy states across Home Assistant restarts.</li>
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

<h2 id="energy-dashboard">📊 Energy Dashboard Setup</h2>

<p>To see your data in the Energy Dashboard, configure the following sensors:</p>

<table>
    <thead>
        <tr>
            <th>Dashboard Section</th>
            <th>Select Sensor</th>
            <th>Entity ID Example</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>Grid Consumption</strong></td>
            <td>Energa Import (Total)</td>
            <td><code>sensor.energa_import_total_...</code></td>
        </tr>
        <tr>
            <td><strong>Return to Grid</strong></td>
            <td>Energa Export (Total)</td>
            <td><code>sensor.energa_export_total_...</code></td>
        </tr>
    </tbody>
</table>

> [!TIP]
> Do NOT use `daily_pobor` or raw meter reading (`total_plus`) for the Energy Dashboard. Use the specific `_total` sensors listed above.

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
    <li><strong>Data Not Appearing?</strong> Ensure you selected the correct `_total` sensors in the Dashboard.</li>
    <li><strong>Yellow Warnings?</strong> Warnings about <code>mean_type</code> in logs are harmless deprecation notices from Home Assistant.</li>
</ul>

<h3>Disclaimer</h3>
<p>This is a custom integration and is not affiliated with Energa Operator. Use at your own risk.</p>
