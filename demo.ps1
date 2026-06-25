# ============================================================
# Z-Sentinel IDS — Demo Script cho PowerShell (Windows)
# Thay the lenh curl tren Linux/Mac
# ============================================================
param([string]$Action = "help")

$BASE    = "http://localhost:8000"
$API_KEY = if ($env:IDS_API_KEY) { $env:IDS_API_KEY } else { "changeme-set-API_KEY-in-env" }
$HEADERS = @{ "X-API-Key" = $API_KEY }

switch ($Action.ToLower()) {

    "health" {
        Write-Host "`n=== Health Check ===" -ForegroundColor Cyan
        Invoke-RestMethod "$BASE/health/detailed" -Method GET | ConvertTo-Json
    }

    "demo-start" {
        Write-Host "`n=== Starting Attack Replay Demo ===" -ForegroundColor Yellow
        Invoke-RestMethod "$BASE/api/demo/start?delay_sec=0.5&rounds=2&unique_src=true" -Method POST | ConvertTo-Json
    }

    "demo-start-fast" {
        Write-Host "`n=== Starting FAST Demo (0.2s delay) ===" -ForegroundColor Yellow
        Invoke-RestMethod "$BASE/api/demo/start?delay_sec=0.2&rounds=3&unique_src=true" -Method POST | ConvertTo-Json
    }

    "demo-stop" {
        Write-Host "`n=== Stopping Demo ===" -ForegroundColor Red
        Invoke-RestMethod "$BASE/api/demo/stop" -Method POST | ConvertTo-Json
    }

    "demo-status" {
        Write-Host "`n=== Demo Status ===" -ForegroundColor Cyan
        Invoke-RestMethod "$BASE/api/demo/status" -Method GET | ConvertTo-Json
    }

    "alerts" {
        Write-Host "`n=== Recent Alerts (last 10) ===" -ForegroundColor Magenta
        $list = Invoke-RestMethod "$BASE/api/alerts/?limit=10" -Method GET
        foreach ($a in $list) {
            $clr = switch ($a.severity) {
                "critical" { "Red" }
                "high"     { "DarkYellow" }
                "medium"   { "Yellow" }
                default    { "Gray" }
            }
            $conf = [math]::Round($a.confidence * 100, 1)
            Write-Host "[$($a.severity.ToUpper())] $($a.attack_type) from $($a.source_ip) conf=$conf%" -ForegroundColor $clr
        }
        if (-not $list) { Write-Host "No alerts yet." -ForegroundColor Gray }
    }

    "interfaces" {
        Write-Host "`n=== Network Interfaces ===" -ForegroundColor Cyan
        Invoke-RestMethod "$BASE/api/sniffer/interfaces" -Method GET -Headers $HEADERS | ConvertTo-Json
    }

    "pipeline-start" {
        $iface = if ($args[0]) { $args[0] } else { "Wi-Fi 2" }
        Write-Host "`n=== Starting Pipeline on '$iface' ===" -ForegroundColor Green
        Invoke-RestMethod "$BASE/api/sniffer/start?interface=$([uri]::EscapeDataString($iface))" -Method POST -Headers $HEADERS | ConvertTo-Json
    }

    "pipeline-stop" {
        Write-Host "`n=== Stopping Pipeline ===" -ForegroundColor Red
        Invoke-RestMethod "$BASE/api/sniffer/stop" -Method POST -Headers $HEADERS | ConvertTo-Json
    }

    "pipeline-status" {
        Write-Host "`n=== Pipeline Status ===" -ForegroundColor Cyan
        Invoke-RestMethod "$BASE/api/sniffer/status" -Method GET -Headers $HEADERS | ConvertTo-Json
    }

    "stats" {
        Write-Host "`n=== Dashboard Stats ===" -ForegroundColor Cyan
        Invoke-RestMethod "$BASE/api/stats/dashboard" -Method GET | ConvertTo-Json
    }

    default {
        Write-Host @"

Z-Sentinel IDS — Demo PowerShell Commands
==========================================
Chay: .\demo.ps1 -Action <lenh>

  health           Kiem tra trang thai backend
  demo-start       Bat dau demo tan cong (delay=0.5s, 2 rounds)
  demo-start-fast  Bat dau demo nhanh   (delay=0.2s, 3 rounds)
  demo-stop        Dung demo
  demo-status      Trang thai demo hien tai
  alerts           Xem 10 alert gan nhat
  stats            Dashboard stats
  interfaces       Liet ke network interfaces
  pipeline-start   Bat dau sniff goi tin that (can Npcap + admin)
  pipeline-stop    Dung pipeline
  pipeline-status  Trang thai pipeline

Vi du demo bao ve:
  .\demo.ps1 -Action demo-start
  (Mo browser: http://localhost:3000 -> tab Overview)
  .\demo.ps1 -Action demo-status
  .\demo.ps1 -Action alerts
"@ -ForegroundColor White
    }
}
