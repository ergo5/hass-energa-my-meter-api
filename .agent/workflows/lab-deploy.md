---
description: Deploy custom integration to Lab HA (192.168.70.199) via L:\ drive
---

# Deploy Integration to Lab HA

Deploy a custom integration to the Lab Home Assistant instance using the L:\ drive (SMB mount to \\192.168.70.199\config).

## Prerequisites
- L:\ drive must be mapped (`net use L: \\192.168.70.199\config`)
- Lab HA API token from KI: `mcp_and_api_credentials.md`

## Steps

### 1. Copy files to Lab via L:\
// turbo
```powershell
Copy-Item "d:\Temp\<REPO>\custom_components\<INTEGRATION>\*.py" "L:\custom_components\<INTEGRATION>\" -Force
Copy-Item "d:\Temp\<REPO>\custom_components\<INTEGRATION>\manifest.json" "L:\custom_components\<INTEGRATION>\" -Force
Write-Host "Deploy OK"
Get-Content "L:\custom_components\<INTEGRATION>\manifest.json"
```
Replace `<REPO>` and `<INTEGRATION>` with the actual repo directory and integration domain.

### 2. Restart HA via REST API
```powershell
$token = "<LLAT_TOKEN>"
$h = @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" }
try { Invoke-RestMethod -Uri "http://192.168.70.199:8123/api/services/homeassistant/restart" -Method POST -Headers $h -Body '{}' -TimeoutSec 15 } catch {}
Write-Host "Restart sent"
```

### 3. Wait for HA to come back
// turbo
```powershell
$token = "<LLAT_TOKEN>"
$h = @{ "Authorization" = "Bearer $token" }
Start-Sleep 40
for ($i=0; $i -lt 12; $i++) {
    Start-Sleep 5
    try {
        $r = Invoke-RestMethod -Uri "http://192.168.70.199:8123/api/" -Headers $h -TimeoutSec 5
        if ($r.message -eq "API running.") { Write-Host "HA UP after $((40+$i*5+5))s"; break }
    } catch { Write-Host "Waiting... $((40+$i*5+5))s" }
}
```

### 4. Verify deployment
// turbo
```powershell
$token = "<LLAT_TOKEN>"
$h = @{ "Authorization" = "Bearer $token" }
$states = Invoke-RestMethod -Uri "http://192.168.70.199:8123/api/states" -Headers $h
$entities = $states | Where-Object { $_.entity_id -like "sensor.<INTEGRATION_PREFIX>*" } | Select-Object entity_id, @{N="state";E={$_.state}} | Sort-Object entity_id
$entities | Format-Table -AutoSize
```

## Important Notes
- **Do NOT use SSH for file transfer** — Lab HA SSH addon has no SFTP subsystem; SCP fails.
- **Do NOT use MCP filesystem** — permission denied (files owned by root, Incident #30).
- **L:\ is the only reliable file channel** for Lab HA.
- **504 Gateway Timeout on restart is normal** — HA shuts down before responding.
- After restart, wait ~40-60s before polling API.
- Always get the token from KI `mcp_and_api_credentials.md`, never hardcode.
