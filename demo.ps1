# ============================================================
# Z-Sentinel IDS — Demo Script (PowerShell)
# Kịch bản demo hoàn chỉnh cho buổi bảo vệ luận văn
# ============================================================
param([string]$Action = "help")

$BASE    = "http://localhost:8000"
$API_KEY = if ($env:IDS_API_KEY) { $env:IDS_API_KEY } else { "changeme-set-API_KEY-in-env" }
$HEADERS = @{ "X-API-Key" = $API_KEY }

function Write-Step { param($n, $msg)
  Write-Host "`n[$n] $msg" -ForegroundColor Cyan
}
function Write-OK   { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-WARN { param($msg) Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-INFO { param($msg) Write-Host "  → $msg" -ForegroundColor Gray }

switch ($Action.ToLower()) {

  # ── Health ──────────────────────────────────────────────────────────────
  "health" {
    Write-Step 1 "Kiểm tra trạng thái hệ thống"
    $h = Invoke-RestMethod "$BASE/health/detailed" -Method GET
    Write-OK  "Backend: $($h.model_loaded -eq $true ? 'ML Model loaded' : 'running')"
    Write-OK  "PostgreSQL: $($h.postgres.connected ? 'connected' : 'ERROR')"
    Write-OK  "Cache: $($h.cache.connected ? 'connected' : 'in-memory')"
    Write-INFO "Pipeline running: $($h.pipeline_running)"
    $h | ConvertTo-Json
  }

  # ── Demo tấn công ────────────────────────────────────────────────────────
  "demo-start" {
    Write-Step 1 "Bắt đầu demo tấn công (delay=0.5s, 2 rounds)"
    $r = Invoke-RestMethod "$BASE/api/demo/start?delay_sec=0.5&rounds=2&unique_src=true" -Method POST
    Write-OK "Demo started: $($r.samples_per_round) samples/round"
    Write-INFO "Mở http://localhost:3000 → tab Cảnh báo để xem real-time alerts"
    $r | ConvertTo-Json
  }

  "demo-start-fast" {
    Write-Step 1 "Demo nhanh (delay=0.2s, 3 rounds)"
    $r = Invoke-RestMethod "$BASE/api/demo/start?delay_sec=0.2&rounds=3&unique_src=true" -Method POST
    Write-OK "Demo started"
    $r | ConvertTo-Json
  }

  "demo-ddos" {
    Write-Step 1 "Demo chỉ DDoS (rõ ràng nhất)"
    $r = Invoke-RestMethod "$BASE/api/demo/start?classes=DDoS&delay_sec=0.3&rounds=2&unique_src=true" -Method POST
    Write-OK "DDoS demo started"
    $r | ConvertTo-Json
  }

  "demo-campaign" {
    Write-Step 1 "Demo Attack Campaign (PortScan → BruteForce → DDoS)"
    Write-INFO "Round 1: PortScan"
    Invoke-RestMethod "$BASE/api/demo/start?classes=PortScan&delay_sec=0.3&rounds=1&unique_src=false" -Method POST | Out-Null
    Start-Sleep -Seconds 8
    Write-INFO "Round 2: BruteForce từ cùng IP"
    Invoke-RestMethod "$BASE/api/demo/start?classes=BruteForce&delay_sec=0.3&rounds=1&unique_src=false" -Method POST | Out-Null
    Start-Sleep -Seconds 8
    Write-INFO "Round 3: DDoS → trigger correlation"
    Invoke-RestMethod "$BASE/api/demo/start?classes=DDoS&delay_sec=0.3&rounds=1&unique_src=false" -Method POST | Out-Null
    Write-OK "Campaign demo running — check 'Cảnh báo' tab for escalated severity"
  }

  "demo-stop" {
    Write-Step 1 "Dừng demo"
    $r = Invoke-RestMethod "$BASE/api/demo/stop" -Method POST
    Write-OK $r.message
    $r | ConvertTo-Json
  }

  "demo-status" {
    Write-Step 1 "Trạng thái demo"
    $s = Invoke-RestMethod "$BASE/api/demo/status" -Method GET
    Write-INFO "Running    : $($s.running)"
    Write-INFO "Replayed   : $($s.replayed) / $($s.samples_total)"
    Write-INFO "Detected   : $($s.detected_attacks)"
    Write-INFO "Broadcast  : $($s.alerts_broadcast)"
    Write-INFO "Suppressed : $($s.suppressed)"
    if ($s.by_class) {
      Write-INFO "By class   : $($s.by_class | ConvertTo-Json -Compress)"
    }
  }

  # ── Alerts ──────────────────────────────────────────────────────────────
  "alerts" {
    Write-Step 1 "10 cảnh báo gần nhất"
    $list = Invoke-RestMethod "$BASE/api/alerts/?limit=10" -Method GET
    if (-not $list) { Write-WARN "Không có alert nào"; break }
    foreach ($a in $list) {
      $clr = switch ($a.severity) {
        "critical" { "Red" } "high" { "DarkYellow" } "medium" { "Yellow" } default { "Gray" }
      }
      $conf = [math]::Round($a.confidence * 100, 1)
      Write-Host ("  [{0,-8}] {1,-15} src={2,-18} conf={3}%" -f
        $a.severity.ToUpper(), $a.attack_type, $a.source_ip, $conf) -ForegroundColor $clr
    }
  }

  "alert-stats" {
    Write-Step 1 "Thống kê Alert Engine"
    $s = Invoke-RestMethod "$BASE/api/stats/alert-engine" -Method GET
    Write-INFO "Total alerts    : $($s.total_alerts)"
    Write-INFO "Active attackers: $($s.active_attackers)"
    Write-INFO "Active campaigns: $($s.active_campaigns)"
    Write-INFO "Auto-block      : $($s.auto_block_enabled) (threshold: $($s.auto_block_threshold))"
    if ($s.campaigns -and $s.campaigns.PSObject.Properties.Count -gt 0) {
      Write-Host "`n  Campaigns:" -ForegroundColor Magenta
      $s.campaigns.PSObject.Properties | ForEach-Object {
        Write-Host "    $($_.Name): $($_.Value | ConvertTo-Json -Compress)" -ForegroundColor Magenta
      }
    }
  }

  # ── Firewall / Blacklist ─────────────────────────────────────────────────
  "blacklist" {
    Write-Step 1 "Danh sách IP bị chặn"
    $bl = Invoke-RestMethod "$BASE/api/blacklist/" -Method GET
    if ($bl.Count -eq 0) { Write-INFO "Không có IP bị chặn"; break }
    foreach ($item in $bl) {
      $exp = if ($item.expires_at) { $item.expires_at.Substring(0,19) } else { "Vĩnh viễn" }
      Write-Host ("  {0,-18} | {1,-10} | {2}" -f $item.ip_address, ($item.auto_blocked ? "Auto" : "Manual"), $exp) -ForegroundColor Red
    }
  }

  "clear-demo-data" {
    Write-Step 1 "Xóa dữ liệu demo (alerts + blacklist)"
    Write-WARN "Thao tác này sẽ xóa TẤT CẢ alerts và IP blocks!"
    $confirm = Read-Host "Nhập 'yes' để xác nhận"
    if ($confirm -ne "yes") { Write-WARN "Đã hủy"; break }
    # Xóa alerts
    $alerts = Invoke-RestMethod "$BASE/api/alerts/?limit=500" -Method GET
    $deleted = 0
    foreach ($a in $alerts) {
      try { Invoke-RestMethod "$BASE/api/alerts/$($a.alert_id)" -Method DELETE -Headers $HEADERS | Out-Null; $deleted++ }
      catch {}
    }
    Write-OK "Đã xóa $deleted alerts"
    # Xóa blacklist
    $bl = Invoke-RestMethod "$BASE/api/blacklist/" -Method GET
    $unblocked = 0
    foreach ($item in $bl) {
      try { Invoke-RestMethod "$BASE/api/blacklist/$($item.ip_address)" -Method DELETE | Out-Null; $unblocked++ }
      catch {}
    }
    Write-OK "Đã gỡ chặn $unblocked IPs"
  }

  # ── Stats ────────────────────────────────────────────────────────────────
  "stats" {
    Write-Step 1 "Dashboard stats (24h)"
    $s = Invoke-RestMethod "$BASE/api/stats/dashboard" -Method GET
    Write-INFO "Servers       : $($s.total_servers)"
    Write-INFO "Total alerts  : $($s.total_alerts)"
    Write-INFO "Active alerts : $($s.active_alerts)"
    Write-INFO "Blocked IPs   : $($s.blocked_ips)"
    if ($s.threat_categories) {
      Write-Host "`n  Attack types:" -ForegroundColor Yellow
      foreach ($t in $s.threat_categories) {
        Write-Host ("    {0,-15} {1}" -f $t.type, $t.count) -ForegroundColor Yellow
      }
    }
  }

  # ── Sniffer (packet capture thật) ───────────────────────────────────────
  "interfaces" {
    Write-Step 1 "Danh sách network interfaces"
    $r = Invoke-RestMethod "$BASE/api/sniffer/interfaces" -Method GET -Headers $HEADERS
    $r.interfaces | ForEach-Object { Write-INFO $_ }
  }

  "pipeline-start" {
    $iface = if ($args[0]) { $args[0] } else { "Wi-Fi" }
    Write-Step 1 "Bắt đầu packet capture trên '$iface'"
    Write-WARN "Cần Npcap + quyền Administrator!"
    $r = Invoke-RestMethod "$BASE/api/sniffer/start?interface=$([uri]::EscapeDataString($iface))" -Method POST -Headers $HEADERS
    $r | ConvertTo-Json
  }

  "pipeline-stop" {
    Write-Step 1 "Dừng pipeline"
    $r = Invoke-RestMethod "$BASE/api/sniffer/stop" -Method POST -Headers $HEADERS
    Write-OK $r.message
  }

  "pipeline-status" {
    Write-Step 1 "Trạng thái pipeline"
    $s = Invoke-RestMethod "$BASE/api/sniffer/status" -Method GET -Headers $HEADERS
    Write-INFO "Running  : $($s.is_running)"
    Write-INFO "Packets  : $($s.processed_packets)"
    Write-INFO "Inferences: $($s.inference_runs)"
    $s | ConvertTo-Json
  }

  # ── Simulate attack ──────────────────────────────────────────────────────
  "simulate" {
    $type = if ($args[0]) { $args[0] } else { "all" }
    Write-Step 1 "Giả lập tấn công: $type"
    python backend/scripts/simulate_attack.py --type $type --delay 0.3
  }

  "simulate-ddos"  { python backend/scripts/simulate_attack.py --type DDoS     --count 2 --delay 0.3 }
  "simulate-scan"  { python backend/scripts/simulate_attack.py --type PortScan  --delay 0.3 }
  "simulate-brute" { python backend/scripts/simulate_attack.py --type BruteForce --delay 0.3 }

  # ── Full demo tự động ────────────────────────────────────────────────────
  "full-demo" {
    Write-Host "`n$('='*60)" -ForegroundColor Cyan
    Write-Host "  Z-SENTINEL IDS — FULL DEMO TỰ ĐỘNG" -ForegroundColor Cyan
    Write-Host "$('='*60)`n" -ForegroundColor Cyan

    # 1. Health check
    Write-Step "1/8" "Kiểm tra hệ thống"
    try {
      $h = Invoke-RestMethod "$BASE/health/detailed" -Method GET
      Write-OK "Backend healthy | DB: $($h.postgres.connected) | Model: $($h.model_loaded)"
    } catch {
      Write-Host "  ✗ Backend không khả dụng! Hãy khởi động backend trước." -ForegroundColor Red
      exit 1
    }

    # 2. Dashboard stats ban đầu
    Write-Step "2/8" "Trạng thái ban đầu"
    $s = Invoke-RestMethod "$BASE/api/stats/dashboard" -Method GET
    Write-INFO "Servers: $($s.total_servers) | Alerts: $($s.total_alerts) | Blocked: $($s.blocked_ips)"

    # 3. Bắt đầu demo DDoS
    Write-Step "3/8" "Phát động tấn công DDoS (2 rounds × 16 samples)"
    Invoke-RestMethod "$BASE/api/demo/start?classes=DDoS&delay_sec=0.4&rounds=2&unique_src=true" -Method POST | Out-Null
    Write-OK "Demo DDoS started → xem Live Alert Feed trên Dashboard"
    Write-INFO "→ http://localhost:3000 → tab Cảnh báo"

    # 4. Chờ DDoS hoàn thành
    Write-Step "4/8" "Đợi DDoS hoàn thành..."
    $wait = 0
    do {
      Start-Sleep -Seconds 3; $wait += 3
      $ds = Invoke-RestMethod "$BASE/api/demo/status" -Method GET
      Write-INFO "  replayed=$($ds.replayed) broadcast=$($ds.alerts_broadcast) [$wait`s]"
    } while ($ds.running -and $wait -lt 45)
    Write-OK "DDoS demo: $($ds.alerts_broadcast) alerts broadcast"

    # 5. Campaign: PortScan + BruteForce
    Write-Step "5/8" "Demo Attack Campaign (PortScan → BruteForce)"
    Invoke-RestMethod "$BASE/api/demo/start?classes=PortScan,BruteForce&delay_sec=0.3&rounds=1&unique_src=false" -Method POST | Out-Null
    Start-Sleep -Seconds 12
    Write-OK "Campaign demo sent — correlation engine sẽ tăng severity"

    # 6. Xem alerts
    Write-Step "6/8" "Kết quả cảnh báo"
    $alerts = Invoke-RestMethod "$BASE/api/alerts/?limit=5" -Method GET
    foreach ($a in $alerts) {
      $conf = [math]::Round($a.confidence * 100, 1)
      $clr = switch ($a.severity) { "critical" { "Red" } "high" { "DarkYellow" } default { "Gray" } }
      Write-Host ("    [{0,-8}] {1,-15} {2,-18} {3}%" -f $a.severity.ToUpper(), $a.attack_type, $a.source_ip, $conf) -ForegroundColor $clr
    }

    # 7. Alert engine stats
    Write-Step "7/8" "Alert Engine Statistics"
    $as = Invoke-RestMethod "$BASE/api/stats/alert-engine" -Method GET
    Write-INFO "Total alerts    : $($as.total_alerts)"
    Write-INFO "Active attackers: $($as.active_attackers)"
    Write-INFO "Active campaigns: $($as.active_campaigns)"

    # 8. Tổng kết
    Write-Step "8/8" "Tổng kết"
    $final = Invoke-RestMethod "$BASE/api/stats/dashboard" -Method GET
    Write-Host "`n  ┌──────────────────────────────────┐" -ForegroundColor Green
    Write-Host "  │  KẾT QUẢ DEMO                    │" -ForegroundColor Green
    Write-Host "  ├──────────────────────────────────┤" -ForegroundColor Green
    Write-Host ("  │  Tổng alerts    : {0,-16}│" -f $final.total_alerts) -ForegroundColor Green
    Write-Host ("  │  Đang hoạt động : {0,-16}│" -f $final.active_alerts) -ForegroundColor Green
    Write-Host ("  │  IP bị chặn     : {0,-16}│" -f $final.blocked_ips) -ForegroundColor Green
    Write-Host "  └──────────────────────────────────┘" -ForegroundColor Green
    Write-Host "`n  ➜ Mở Dashboard: http://localhost:3000" -ForegroundColor Cyan
    Write-Host "  ➜ Tab AI Insights: Bấm 'Run Explanation' để xem SHAP" -ForegroundColor Cyan
    Write-Host "  ➜ Tab Báo cáo: Bấm 'Generate' để xuất báo cáo" -ForegroundColor Cyan
  }

  # ── Tailscale ────────────────────────────────────────────────────────────
  "tailscale-ip" {
    Write-Step 1 "Lấy Tailscale IP của laptop này"
    try {
      $ts = Invoke-RestMethod "http://localhost:41112/localapi/v0/status" -Method GET
      $self = $ts.Self
      Write-OK "Tailscale IP: $($self.TailscaleIPs[0])"
      Write-INFO "Agent trên điện thoại dùng:"
      Write-Host "  IDS_API_URL=http://$($self.TailscaleIPs[0]):8000/api/servers" -ForegroundColor Cyan
    } catch {
      Write-WARN "Tailscale chưa chạy hoặc chưa cài"
      Write-INFO "Tải tại: https://tailscale.com/download/windows"
    }
  }

  "tailscale-check" {
    Write-Step 1 "Kiểm tra kết nối Tailscale"
    try {
      $ts = Invoke-RestMethod "http://localhost:41112/localapi/v0/status" -Method GET
      Write-OK "Tailscale online: $($ts.Self.TailscaleIPs[0])"
      Write-INFO "Peers:"
      foreach ($peer in $ts.Peer.PSObject.Properties) {
        $p = $peer.Value
        Write-Host ("    {0,-20} {1,-15} {2}" -f $p.HostName, $p.TailscaleIPs[0], ($p.Online ? "ONLINE" : "offline")) -ForegroundColor ($p.Online ? "Green" : "Gray")
      }
    } catch {
      Write-WARN "Tailscale không khả dụng"
    }
  }

  # ── Help ─────────────────────────────────────────────────────────────────
  default {
    Write-Host @"

Z-Sentinel IDS — Demo Script
==============================
Cách dùng: .\demo.ps1 -Action <lenh>

DEMO COMMANDS:
  full-demo        Chạy toàn bộ kịch bản tự động (10 phút)
  demo-start       Demo tấn công đa loại (0.5s delay, 2 rounds)
  demo-start-fast  Demo nhanh (0.2s delay, 3 rounds)
  demo-ddos        Chỉ demo DDoS
  demo-campaign    Demo attack campaign đa bước (Scan→BruteForce→DDoS)
  demo-stop        Dừng demo đang chạy
  demo-status      Xem tiến trình demo

MONITORING:
  health           Kiểm tra trạng thái backend
  alerts           Xem 10 alert gần nhất (màu theo severity)
  alert-stats      Thống kê Alert Engine + campaigns
  stats            Dashboard stats (24h)
  blacklist        Danh sách IP đang bị chặn

PIPELINE (cần Npcap + Admin):
  interfaces       Liệt kê network interfaces
  pipeline-start   Bắt đầu sniff gói tin thật
  pipeline-stop    Dừng pipeline
  pipeline-status  Trạng thái pipeline

SIMULATE:
  simulate         Giả lập tấn công (default: all types)
  simulate-ddos    Chỉ DDoS
  simulate-scan    Chỉ Port Scan
  simulate-brute   Chỉ Brute Force

MAINTENANCE:
  clear-demo-data  Xóa toàn bộ alerts + unblock IPs (cần xác nhận)

TIPS:
  .\demo.ps1 -Action full-demo          # Chạy demo tự động
  .\demo.ps1 -Action demo-campaign      # Demo campaign tinh tế nhất
  (Mở browser: http://localhost:3000)
"@ -ForegroundColor White
  }
}
