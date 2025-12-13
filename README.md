<div align="center">
  <img src="/logo.png" alt="Energa Mobile API Logo" width="300"/>
</div>




<h1 align="center">Energa Mobile Integration for Home Assistant</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Badge"></a>
  <img src="https://img.shields.io/badge/version-v3.5.4-blue" alt="Version Badge">
</p>

<p align="center">
  A robust integration for <strong>Energa Operator</strong> meters in Home Assistant, featuring <strong>database resilience</strong> and stable data import for the Energy Dashboard. This version ensures full compliance with HA's modern statistical requirements.
</p>

---

<h3 style="color:red; border-left: 5px solid red; padding-left: 10px;">🚨 Critical Configuration Change (v3.5.5)</h3>

<p>
Due to persistent issues with Home Assistant's database caching—which corrupted the metadata of older sensors—the <strong>Energy Dashboard configuration MUST be updated</strong> to use the new, clean entity IDs. Failing to switch to these new sensors will result in no historical or live data appearing in the Energy Dashboard.
</p>

<h4 style="color:#007bff;">⚠️ Action Required: Update Energy Dashboard Sources</h4>

<p>
You must manually switch the source sensors in your Energy Dashboard configuration to the new ones created by the <code>v3.5.5</code> integration:
</p>

<ol>
    <li>Go to <strong>Settings</strong> &rarr; <strong>Dashboards</strong> &rarr; <strong>Energy</strong>.</li>
    <li>
        <strong>Remove Old Sensors:</strong> Find and delete any sensor starting with <code>sensor.panel_energii_...</code> or <code>sensor.energa_pobor_dzis</code>.
    </li>
    <li>
        <strong>Add New Import Source (Consumption):</strong>
        <ul>
            <li>Under <strong>Grid Consumption</strong>, click "Add consumption".</li>
            <li>Select the new sensor: 
                <span style="background-color:#fff0f5; padding: 2px 5px; border-radius: 3px; font-family: monospace;">Energa Import (Total)</span> 
                (Entity ID: <code>sensor.energa_import_total_...</code>)
            </li>
        </ul>
    </li>
    <li>
        <strong>Add New Export Source (Return to Grid):</strong>
        <ul>
            <li>Under <strong>Return to Grid</strong>, click "Add solar production".</li>
            <li>Select the new sensor: 
                <span style="background-color:#fff0f5; padding: 2px 5px; border-radius: 3px; font-family: monospace;">Energa Export (Total)</span> 
                (Entity ID: <code>sensor.energa_export_total_...</code>)
            </li>
        </ul>
    </li>
</ol>

<p>
<strong>Result:</strong> After this step, the Energy Dashboard will start reading data from the clean sensor IDs, allowing both live data and previously imported history to display correctly.
</p>

<h2 id="key-features">✨ Key Features (v3.5.x)</h2>

<ul>
    <li><strong>📊 Stable History Import:</strong> Logic is strictly compliant with HA's <code>total_increasing</code> statistical rules for correct data aggregation.</li>
    <li><strong>🛡️ Database Resilience:</strong> Uses unique entity IDs (<code>_import_total</code>) to prevent conflicts with old, corrupted metadata in the Home Assistant database.</li>
    <li><strong>🔄 Restart Proof:</strong> Employs <code>RestoreEntity</code> to maintain the last known energy state across HA restarts, preventing data gaps or false resets.</li>
    <li><strong>⚡ Hourly Granularity:</strong> Consumption is calculated from hourly data charts for precise energy tracking.</li>
    <li><strong>🔍 OBIS Auto-Detect:</strong> Automatically identifies Import (1.8.0) and Export (2.8.0) registers.</li>
</ul>

---

<h2 id="installation">📦 Installation & Configuration</h2>

<h3>Option 1: HACS (Recommended for Updates)</h3>
<ol>
    <li>Open <strong>HACS</strong> in Home Assistant.</li>
    <li>Go to <strong>Integrations</strong> &rarr; <strong>Custom repositories</strong>.</li>
    <li>Add this repository URL: <code>https://github.com/ergo5/hass-energa-my-meter-api</code></li>
    <li>Select the category: <strong>Integration</strong>.</li>
    <li>Once added, search for and install <strong>Energa Mobile Integration</strong>.</li>
    <li><strong>Restart Home Assistant.</strong></li>
</ol>

<h3>Option 2: Manual Installation</h3>
<ol>
    <li>Download the <code>energa_mobile</code> folder from the latest release.</li>
    <li>Copy the folder to your Home Assistant <code>/config/custom_components</code> directory.</li>
    <li><strong>Restart Home Assistant.</strong></li>
</ol>

<h3>Configuration</h3>
<ol>
    <li>Go to <strong>Settings</strong> &rarr; <strong>Devices & Services</strong>.</li>
    <li>Search for <strong>Energa Mobile</strong>.</li>
    <li>Enter your <strong>Energa Mój Licznik</strong> username (email) and password to log in.</li>
</ol>

---

<h2 id="entities-dashboard">3. 📊 Entities & Energy Dashboard (CRITICAL STEP)</h2>

<p>
Use the new <code>_total</code> sensors for the Energy Dashboard. These have been specifically optimized for the HA Recorder component.
</p>

<table>
    <thead>
        <tr>
            <th>Sensor Name</th>
            <th>Entity ID (Pattern)</th>
            <th>HA Class</th>
            <th>Purpose</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>Energa Import (Total)</strong></td>
            <td><code>sensor.energa_import_total_...</code></td>
            <td><code>total_increasing</code></td>
            <td><strong>Primary Source</strong> for Grid Consumption.</td>
        </tr>
        <tr>
            <td><strong>Energa Export (Total)</strong></td>
            <td><code>sensor.energa_export_total_...</code></td>
            <td><code>total_increasing</code></td>
            <td><strong>Primary Source</strong> for Return to Grid.</td>
        </tr>
        <tr>
            <td>Stan Licznika - Pobór</td>
            <td><code>sensor.total_plus_...</code></td>
            <td><code>total_increasing</code></td>
            <td>Raw Meter Index (For informational use only).</td>
        </tr>
    </tbody>
</table>

<h3>🚨 Configuring the Energy Dashboard</h3>
<ol>
    <li>Go to <strong>Settings</strong> &rarr; <strong>Dashboards</strong> &rarr; <strong>Energy</strong>.</li>
    <li>Under <strong>Grid Consumption</strong>, add: <strong><code>Energa Import (Total)</code></strong>.</li>
    <li>Under <strong>Return to Grid</strong>, add: <strong><code>Energa Export (Total)</code></strong>.</li>
</ol>

---

<h2 id="import-history">4. 📅 How to Import History (Backfill)</h2>

<p>
This step is required once to populate the Dashboard with past data.
</p>

<ol>
    <li>Go to <strong>Settings</strong> &rarr; <strong>Devices & Services</strong>.</li>
    <li>Find <strong>Energa Mobile</strong> and click <strong>Configure</strong>.</li>
    <li>Select <strong>"Pobierz Historię" (Download History)</strong>.</li>
    <li>Select the <strong>Start Date</strong> (e.g., <code>2024-11-01</code>).</li>
    <li>Click <strong>Submit</strong>.</li>
</ol>

<p>
<strong>Note:</strong> The API may limit historic data visibility (often 30-60 days). The data will appear in the Energy Dashboard after Home Assistant finishes processing (15-60 minutes).
</p>

---

<h2 id="troubleshooting">5. 🐛 Troubleshooting & Known Issues</h2>

<h3>🟡 Yellow Warnings in Logs (Harmless)</h3>
<p>
If you see warnings about <code>mean_type</code> (e.g., <em>"...doesn't specify mean_type..."</em>):
</p>
<ul>
    <li><strong>Ignore them.</strong> This is a future deprecation warning from Home Assistant. It does not affect current functionality and is visible because the integration avoids the parameter that previously caused critical database errors.</li>
</ul>

<h3>🛑 History Not Appearing?</h3>
<p>
If data does not appear after import, it is likely due to old database entries.
</p>
<ol>
    <li><strong>Clean up old sensors:</strong> In <strong>Developer Tools</strong> &rarr; <strong>Statistics</strong>, ensure all previously created, non-functional sensors (e.g., <code>sensor.panel_energii...</code>) are removed using the Trash Can icon to eliminate conflicts.</li>
    <li>Rerun the history import.</li>
</ol>

---

<h3 id="disclaimer">Disclaimer</h3>
<p>This is a custom integration and is not affiliated with Energa Operator. Use at your own risk.</p>
