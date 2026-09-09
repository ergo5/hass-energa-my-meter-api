---
description: Diagnose Lab HA integration state via L:\ drive and REST API (no SSH/MCP dependency)
---

# Lab HA Diagnostics

Run diagnostics on the Lab HA instance without depending on SSH or MCP servers.
Uses L:\ drive (SMB) for filesystem/DB access and REST API for state queries.

## Prerequisites
- L:\ drive mapped to `\\192.168.70.199\config`
- Lab HA API token from KI: `mcp_and_api_credentials.md`
- Python 3 with sqlite3 (built-in)

## Diagnostic Steps

### 1. Check API health
// turbo
```powershell
$token = "<LLAT_TOKEN>"
$h = @{ "Authorization" = "Bearer $token" }
(Invoke-RestMethod -Uri "http://192.168.70.199:8123/api/" -Headers $h -TimeoutSec 5).message
```

### 2. List all entities for integration
// turbo
```powershell
$token = "<LLAT_TOKEN>"
$h = @{ "Authorization" = "Bearer $token" }
$states = Invoke-RestMethod -Uri "http://192.168.70.199:8123/api/states" -Headers $h
$states | Where-Object { $_.entity_id -like "sensor.<PREFIX>*" } | Select-Object entity_id, @{N="state";E={$_.state}} | Sort-Object entity_id | Format-Table -AutoSize
```

### 3. Enable debug logging for integration
```powershell
$token = "<LLAT_TOKEN>"
$h = @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" }
Invoke-RestMethod -Uri "http://192.168.70.199:8123/api/services/logger/set_level" -Method POST -Headers $h -Body '{"custom_components.<DOMAIN>": "debug"}'
Write-Host "Debug logging enabled"
```

### 4. Read HA logs (after enabling logging + waiting for a coordinator cycle)
// turbo
```powershell
# Check if log file exists on L:
if (Test-Path "L:\home-assistant.log") {
    Select-String -Path "L:\home-assistant.log" -Pattern "<KEYWORD>" | Select-Object -Last 30 | ForEach-Object { $_.Line }
} else {
    Write-Host "No log file on L: — logs may be in Docker stdout only."
    Write-Host "Add to configuration.yaml on Lab:"
    Write-Host "  logger:"
    Write-Host "    default: warning"
    Write-Host "    logs:"
    Write-Host "      custom_components.<DOMAIN>: debug"
}
```

### 5. Query statistics from DB (via Python + L:\)
Write a Python script to `$env:TEMP\diag.py` and run it:
```python
import sqlite3
db = r"L:\home-assistant_v2.db"
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
# Example: find all statistics meta for an integration
cur = conn.execute("""
    SELECT id, statistic_id, source, unit_of_measurement
    FROM statistics_meta
    WHERE statistic_id LIKE '%<PREFIX>%'
    ORDER BY statistic_id
""")
for row in cur:
    meta_id, sid, src, unit = row
    last = conn.execute("""
        SELECT datetime(start_ts, 'unixepoch', 'localtime'), state, sum
        FROM statistics WHERE metadata_id=? ORDER BY start_ts DESC LIMIT 3
    """, (meta_id,)).fetchall()
    print(f"META {meta_id}: {sid} ({src}, {unit})")
    for r in last:
        print(f"  {r[0]} | state={r[1]:.4f} | sum={r[2]:.4f}")
conn.close()
```

### 6. Check entity registry for unique_id collisions
```python
import json
with open(r"L:\.storage\core.entity_registry", encoding="utf-8") as f:
    reg = json.load(f)
for e in reg["data"]["entities"]:
    if "<PREFIX>" in e.get("entity_id", ""):
        print(f"{e['entity_id']}")
        print(f"  unique_id={e.get('unique_id')} platform={e.get('platform')}")
```

### 7. Check Energy Dashboard configuration
```python
import json
with open(r"L:\.storage\energy", encoding="utf-8") as f:
    data = json.load(f)
print(json.dumps(data.get("data", {}), indent=2))
```

## Communication Channel Priority (Lab)
1. **L:\ drive (SMB)** — filesystem, DB, .storage — always available
2. **REST API** — entity states, service calls, restart — reliable when HA is up
3. **Python + SQLite** — direct DB queries via L:\ — bypasses MCP/SSH entirely
4. **MCP tools** — convenient but fragile (drops after HA restart, reconnect delays)
5. **SSH** — AVOID for long commands (hangs), no SCP/SFTP support

## Common Issues
- **MCP EOF errors** — HA restarted, MCP connection dropped. Wait 30s, retry.
- **SSH hangs** — Lab SSH addon issue. Terminate and use L:\ instead.
- **Permission denied on L:\** — Files owned by root (Incident #30). Use Python readonly for queries.
- **No home-assistant.log** — Default HA config doesn't write to file. Add `logger:` section to `configuration.yaml`.
