# Demo Firewall Auto-block via Agent Logs Endpoint
# Script này giả lập agent gửi SSH brute force events để test firewall auto-block

$ErrorActionPreference = "Stop"

# Configuration
$API_URL = "http://localhost:8000"
$SERVER_ID = 1
$API_KEY = "changeme"  # Thay bằng API key thực tế từ .env
$ATTACKER_IP = "192.168.1.100"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Firewall Auto-block Demo via Agent Logs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Kiểm tra backend health
Write-Host "[1] Checking backend health..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$API_URL/health" -Method GET
    Write-Host "✓ Backend is healthy" -ForegroundColor Green
} catch {
    Write-Host "✗ Backend is not running. Please start backend first:" -ForegroundColor Red
    Write-Host "  python backend/main.py" -ForegroundColor Gray
    exit 1
}
Write-Host ""

# Step 2: Tạo server test nếu chưa có
Write-Host "[2] Checking/Creating test server..." -ForegroundColor Yellow
try {
    $servers = Invoke-RestMethod -Uri "$API_URL/api/servers" -Method GET
    $testServer = $servers | Where-Object { $_.id -eq $SERVER_ID }
    
    if (-not $testServer) {
        Write-Host "Creating test server (ID: $SERVER_ID)..." -ForegroundColor Gray
        $body = @{
            name = "demo-server"
            ip_address = "192.168.1.1"
            os = "Linux"
            description = "Demo server for firewall testing"
        } | ConvertTo-Json
        
        Invoke-RestMethod -Uri "$API_URL/api/servers" -Method POST -Body $body -ContentType "application/json"
        Write-Host "✓ Test server created" -ForegroundColor Green
    } else {
        Write-Host "✓ Test server exists (ID: $SERVER_ID)" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Failed to create/check server: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 3: Gửi SSH brute force events (25 lần để vượt ngưỡng 20)
Write-Host "[3] Sending SSH brute force events..." -ForegroundColor Yellow
Write-Host "   Attacker IP: $ATTACKER_IP" -ForegroundColor Gray
Write-Host "   Events to send: 25 (threshold: 20 → block 1h)" -ForegroundColor Gray
Write-Host ""

$events = @()
for ($i = 1; $i -le 25; $i++) {
    $events += @{
        event_type = "ssh_brute_force"
        source_ip = $ATTACKER_IP
        count = 1
        severity = if ($i -ge 20) { "critical" } else { "high" }
        message = "SSH brute force: failed login attempt #$i from $ATTACKER_IP"
        log_source = "agent"
    }
}

$payload = @{
    server_id = $SERVER_ID
    events = $events
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Depth 10

try {
    $signature = $null
    # Simple HMAC signature (nếu cần)
    # $hmac = New-Object System.Security.Cryptography.HMACSHA256
    # $hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($API_KEY)
    # $signature = [System.Convert]::ToBase64String($hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($payload)))
    
    $headers = @{
        "X-API-Key" = $API_KEY
        # "X-Signature" = $signature
        "Content-Type" = "application/json"
    }
    
    $response = Invoke-RestMethod -Uri "$API_URL/api/servers/$SERVER_ID/logs" -Method POST -Body $payload -Headers $headers
    Write-Host "✓ Sent 25 events to backend" -ForegroundColor Green
    Write-Host "  Response: $($response.status)" -ForegroundColor Gray
    Write-Host "  Queued events: $($response.queued_events)" -ForegroundColor Gray
} catch {
    Write-Host "✗ Failed to send events: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 4: Đợi batch worker xử lý (5-10 giây)
Write-Host "[4] Waiting for batch worker to process (10s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
Write-Host "✓ Wait completed" -ForegroundColor Green
Write-Host ""

# Step 5: Kiểm tra blacklist
Write-Host "[5] Checking blacklist..." -ForegroundColor Yellow
try {
    $blacklist = Invoke-RestMethod -Uri "$API_URL/api/blacklist" -Method GET
    $blockedIP = $blacklist | Where-Object { $_.ip_address -eq $ATTACKER_IP }
    
    if ($blockedIP) {
        Write-Host "✓ IP $ATTACKER_IP is BLOCKED!" -ForegroundColor Green
        Write-Host "  Reason: $($blockedIP.reason)" -ForegroundColor Gray
        Write-Host "  Auto-blocked: $($blockedIP.auto_blocked)" -ForegroundColor Gray
        Write-Host "  Expires at: $($blockedIP.expires_at)" -ForegroundColor Gray
    } else {
        Write-Host "✗ IP $ATTACKER_IP is NOT blocked yet" -ForegroundColor Yellow
        Write-Host "  Check backend logs for more details" -ForegroundColor Gray
    }
} catch {
    Write-Host "✗ Failed to check blacklist: $_" -ForegroundColor Red
}
Write-Host ""

# Step 6: Kiểm tra security logs
Write-Host "[6] Checking security logs..." -ForegroundColor Yellow
try {
    $logs = Invoke-RestMethod -Uri "$API_URL/api/logs?source_ip=$ATTACKER_IP&limit=5" -Method GET
    Write-Host "✓ Found $($logs.total) logs for IP $ATTACKER_IP" -ForegroundColor Green
    foreach ($log in $logs.items) {
        Write-Host "  - $($log.event_type): $($log.message)" -ForegroundColor Gray
    }
} catch {
    Write-Host "✗ Failed to check logs: $_" -ForegroundColor Red
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Demo completed!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Check backend logs for detailed AlertManager output" -ForegroundColor Gray
Write-Host "2. Open frontend UI to see blocked IP in Blacklist tab" -ForegroundColor Gray
Write-Host "3. To unblock: DELETE /api/blacklist/$ATTACKER_IP" -ForegroundColor Gray
