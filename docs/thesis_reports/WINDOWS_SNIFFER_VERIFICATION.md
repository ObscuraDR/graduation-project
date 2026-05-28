# Windows Packet Sniffer Verification Guide

This guide provides PowerShell commands to verify packet sniffing functionality on Windows.

## Prerequisites

1. **Npcap Installation** (Required)
   ```powershell
   # Download from: https://npcap.com/
   # IMPORTANT: Select "Install Npcap in WinPcap API-compatible Mode" during installation
   ```

2. **Verify Npcap Installation**
   ```powershell
   # Check if Npcap service is running
   Get-Service | Where-Object { $_.DisplayName -like "*npcap*" }
   
   # Expected output: Service with status 'Running'
   ```

## Step 1: List Available Interfaces

```powershell
# Navigate to project directory
cd "d:\graduation project"

# Run interface discovery tool
python backend/scripts/list_interfaces.py
```

**Expected Output:**
```
================================================================================
Available Network Interfaces for Packet Sniffing
================================================================================

Found 2 interface(s):

[1] Wi-Fi
    Description: Wireless Network Connection
    IP Address:  192.168.1.100
    Status:      UP
    *** RECOMMENDED (likely active) ***

[2] Ethernet
    Description: Ethernet Adapter
    IP Address:  192.168.1.101
    Status:      DOWN

================================================================================
Instructions:
================================================================================

To start packet sniffing, use one of the interface names above:

  Recommended: Wi-Fi
  Example API call:
    POST /api/sniffer/start
    {"interface": "Wi-Fi"}
```

## Step 2: Start Backend Server

```powershell
# Start the backend server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 3: Dry Run Test (Recommended First)

```powershell
# Test packet capture for 3 seconds without running full ML pipeline
# This verifies interface permissions and Npcap installation

$headers = @{
    "X-API-Key" = "supersecretkey"
}

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&dry_run=true" -Method POST -Headers $headers

$response | ConvertTo-Json -Depth 10
```

**Expected Success Output:**
```json
{
  "status": "success",
  "message": "Sniffer started on interface Wi-Fi (dry run mode)",
  "interface": "Wi-Fi",
  "filter": "ip",
  "model": "ensemble",
  "min_packets": 10,
  "prediction_mode": "once",
  "prediction_interval_sec": 5.0,
  "flow_expire_sec": 30,
  "dry_run": true
}
```

**Expected Error (Invalid Interface):**
```json
{
  "detail": {
    "error": "Interface 'InvalidInterface' not found. Available interfaces: ['Wi-Fi', 'Ethernet']",
    "requested_interface": "InvalidInterface",
    "available_interfaces": ["Wi-Fi", "Ethernet"]
  }
}
```

**Expected Error (Npcap Not Installed):**
```json
{
  "detail": {
    "error": "No interfaces found. Npcap may not be installed correctly on Windows.",
    "requested_interface": "Wi-Fi",
    "available_interfaces": []
  }
}
```

## Step 4: Check Sniffer Status

```powershell
# Check sniffer status after dry run
$headers = @{
    "X-API-Key" = "supersecretkey"
}

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/sniffer/status" -Method GET -Headers $headers

$response | ConvertTo-Json -Depth 10
```

**Expected Output:**
```json
{
  "is_running": false,
  "interface": "Wi-Fi",
  "filter_expr": "ip",
  "model_name": "ensemble",
  "min_packets": 10,
  "prediction_mode": "once",
  "prediction_interval_sec": 5.0,
  "flow_expire_sec": 30,
  "processed_packets": 0,
  "inference_runs": 0,
  "sniffer_stats": {
    "is_running": false,
    "interface": "Wi-Fi",
    "packets_captured": 150,
    "queue_size": 0,
    "elapsed_seconds": 3.0,
    "packets_per_second": 50.0
  }
}
```

## Step 5: Full Sniffer Start (After Dry Run Success)

```powershell
# Start full IDS pipeline with ML inference
$headers = @{
    "X-API-Key" = "supersecretkey"
}

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&filter_expr=ip&model_name=ensemble&min_packets=10&dry_run=false" -Method POST -Headers $headers

$response | ConvertTo-Json -Depth 10
```

**Expected Output:**
```json
{
  "status": "success",
  "message": "Sniffer started on interface Wi-Fi",
  "interface": "Wi-Fi",
  "filter": "ip",
  "model": "ensemble",
  "min_packets": 10,
  "prediction_mode": "once",
  "prediction_interval_sec": 5.0,
  "flow_expire_sec": 30,
  "dry_run": false
}
```

## Step 6: Monitor Sniffer Status

```powershell
# Monitor sniffer status while running
$headers = @{
    "X-API-Key" = "supersecretkey"
}

while ($true) {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/sniffer/status" -Method GET -Headers $headers
    Clear-Host
    $response | ConvertTo-Json -Depth 10
    Start-Sleep -Seconds 2
}
```

Press `Ctrl+C` to stop monitoring.

## Step 7: Stop Sniffer

```powershell
# Stop the IDS pipeline
$headers = @{
    "X-API-Key" = "supersecretkey"
}

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/sniffer/stop" -Method POST -Headers $headers

$response | ConvertTo-Json -Depth 10
```

**Expected Output:**
```json
{
  "status": "success",
  "message": "Sniffer stopped"
}
```

## Step 8: View Captured Alerts

```powershell
# View alerts generated during sniffing
$headers = @{
    "X-API-Key" = "supersecretkey"
}

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/alerts/" -Method GET -Headers $headers

$response | ConvertTo-Json -Depth 10
```

## Troubleshooting Commands

### Check Npcap Installation

```powershell
# Check if Npcap is installed
Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like "*npcap*" }

# Check Npcap service
Get-Service | Where-Object { $_.DisplayName -like "*npcap*" }
```

### Check Network Interfaces

```powershell
# List all network adapters
Get-NetAdapter

# Check specific adapter status
Get-NetAdapter -Name "Wi-Fi"
```

### Check Python Dependencies

```powershell
# Check if Scapy is installed
python -c "import scapy; print(scapy.__version__)"

# Check if all dependencies are installed
pip list | Select-String -Pattern "scapy"
```

### Test Scapy Directly

```powershell
# Test Scapy interface discovery
python -c "
from scapy.all import get_if_list
if __name__ == '__main__':
    try:
        from scapy.arch.windows import get_windows_if_list
        interfaces = get_windows_if_list()
        for iface in interfaces:
            print(f'Name: {iface.get(\"name\")}, IP: {iface.get(\"ip\")}, UP: {iface.get(\"is_up\")}')
    except Exception as e:
        print(f'Error: {e}')
"
```

### Run Unit Tests

```powershell
# Run interface validation tests
pytest backend/tests/test_sniffer_interface_validation.py -v

# Run all tests
pytest backend/tests/ -v
```

## Common Issues and Solutions

### Issue: "No interfaces found"
**Solution:** 
- Verify Npcap is installed in WinPcap-compatible mode
- Restart computer after Npcap installation
- Run PowerShell as Administrator

### Issue: "Permission denied" or "Access denied"
**Solution:**
- Run PowerShell as Administrator
- Check Windows Firewall settings
- Ensure Npcap service is running

### Issue: Interface name not recognized
**Solution:**
- Use `python backend/scripts/list_interfaces.py` to find exact interface names
- Interface names are case-sensitive on Windows
- Use the exact name shown in the interface list (e.g., "Wi-Fi", not "wi-fi")

### Issue: Dry run succeeds but full sniffer fails
**Solution:**
- Check if ML models are loaded correctly
- Verify `models/` directory contains required files
- Check backend logs for model loading errors

## Verification Checklist

- [ ] Npcap installed in WinPcap-compatible mode
- [ ] Npcap service is running
- [ ] `python backend/scripts/list_interfaces.py` shows available interfaces
- [ ] Dry run test succeeds (captures packets for 3 seconds)
- [ ] Full sniffer start succeeds
- [ ] Sniffer status shows packets being captured
- [ ] Alerts are generated when attack traffic is detected
- [ ] Sniffer stop succeeds cleanly

## Quick Verification Script

Save this as `verify_sniffer.ps1` and run it:

```powershell
# Quick verification script for Windows packet sniffer
Write-Host "=== Windows Packet Sniffer Verification ===" -ForegroundColor Cyan

# 1. Check Npcap
Write-Host "`n[1/5] Checking Npcap installation..." -ForegroundColor Yellow
$npcapService = Get-Service | Where-Object { $_.DisplayName -like "*npcap*" }
if ($npcapService) {
    Write-Host "  Npcap service found: $($npcapService.DisplayName) - Status: $($npcapService.Status)" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Npcap service not found. Install Npcap from https://npcap.com/" -ForegroundColor Red
}

# 2. List interfaces
Write-Host "`n[2/5] Listing available interfaces..." -ForegroundColor Yellow
python backend/scripts/list_interfaces.py

# 3. Check backend health
Write-Host "`n[3/5] Checking backend health..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
    Write-Host "  Backend is healthy" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Backend not running. Start with: uvicorn backend.main:app --reload" -ForegroundColor Red
}

# 4. Dry run test
Write-Host "`n[4/5] Running dry run test..." -ForegroundColor Yellow
$headers = @{ "X-API-Key" = "supersecretkey" }
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&dry_run=true" -Method POST -Headers $headers
    Write-Host "  Dry run started successfully" -ForegroundColor Green
    Start-Sleep -Seconds 4
    Invoke-RestMethod -Uri "http://localhost:8000/api/sniffer/stop" -Method POST -Headers $headers | Out-Null
    Write-Host "  Dry run completed successfully" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Dry run failed: $($_.Exception.Message)" -ForegroundColor Red
}

# 5. Summary
Write-Host "`n[5/5] Verification complete" -ForegroundColor Yellow
Write-Host "If all checks passed, the packet sniffer is ready to use." -ForegroundColor Green
Write-Host "If any checks failed, review the error messages above." -ForegroundColor Yellow
```

Run the verification script:
```powershell
.\verify_sniffer.ps1
```
