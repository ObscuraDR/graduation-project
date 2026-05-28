<#
.SYNOPSIS
    Full End-to-End Demo Automation Script for IDS Backend
    For Thesis Defense - Windows PowerShell

.DESCRIPTION
    This script automates the complete IDS backend demo including:
    - Environment validation
    - Database startup
    - Backend server initialization
    - API security verification
    - Packet sniffing pipeline
    - Alert verification
    - WebSocket testing instructions

.PARAMETER Interface
    Network interface name for packet sniffing (e.g., "Wi-Fi", "Ethernet")

.PARAMETER ApiKey
    API key for authentication (default: from env API_KEY or "demo-key-for-thesis")

.PARAMETER Port
    Backend server port (default: 8000)

.PARAMETER RunDurationSec
    Duration to run sniffer in seconds (default: 15)

.PARAMETER SkipDocker
    Skip Docker database startup

.PARAMETER SkipSniffer
    Skip packet sniffing pipeline

.EXAMPLE
    .\scripts\demo_full.ps1 -Interface "Wi-Fi"
    
.EXAMPLE
    .\scripts\demo_full.ps1 -Interface "Ethernet" -ApiKey "my-secret-key" -Port 8000 -RunDurationSec 30

.EXAMPLE
    .\scripts\demo_full.ps1 -SkipDocker -SkipSniffer
#>

param(
    [string]$Interface = "",
    [string]$ApiKey = "",
    [int]$Port = 8000,
    [int]$RunDurationSec = 15,
    [switch]$SkipDocker,
    [switch]$SkipSniffer
)

# Script configuration
$ErrorActionPreference = "Continue"
$BaseUrl = "http://localhost:$Port"
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Split-Path -Parent $ScriptPath
$ProjectRoot = Split-Path -Parent $BackendDir

# Helper functions
function Write-Checkpoint {
    param(
        [string]$Status,
        [string]$Message
    )
    
    $color = if ($Status -eq "PASS") { "Green" } elseif ($Status -eq "FAIL") { "Red" } else { "Yellow" }
    Write-Host "[$Status] $Message" -ForegroundColor $color
}

function Test-Command {
    param([string]$Command)
    
    try {
        $null = Get-Command $Command -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Invoke-HealthCheck {
    param([int]$MaxAttempts = 30)
    
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $response = curl.exe -s -o /dev/null -w "%{http_code}" "$BaseUrl/health" 2>$null
            if ($response -eq "200") {
                return $true
            }
        } catch {
            # Ignore errors during health check
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-EnvApiKey {
    $envKey = $env:API_KEY
    if ($envKey) {
        return $envKey
    }
    return "demo-key-for-thesis"
}

# Main script
Write-Host "=" * 80
Write-Host "IDS BACKEND - FULL END-TO-END DEMO AUTOMATION"
Write-Host "Thesis Defense Script"
Write-Host "=" * 80
Write-Host ""

# Set API key
if (-not $ApiKey) {
    $ApiKey = Get-EnvApiKey
}
Write-Host "Configuration:"
Write-Host "  Base URL: $BaseUrl"
Write-Host "  API Key: $ApiKey"
Write-Host "  Port: $Port"
Write-Host "  Run Duration: $RunDurationSec seconds"
Write-Host "  Skip Docker: $SkipDocker"
Write-Host "  Skip Sniffer: $SkipSniffer"
Write-Host ""

# ============================================================================
# STAGE A: Validate Environment
# ============================================================================
Write-Host "STAGE A: Environment Validation"
Write-Host "-" * 80

$envValid = $true

# Check Python
if (Test-Command "python") {
    $pythonVersion = python --version 2>&1
    Write-Checkpoint "PASS" "Python found: $pythonVersion"
} else {
    Write-Checkpoint "FAIL" "Python not found. Please install Python 3.8+"
    $envValid = $false
}

# Check Docker
if (Test-Command "docker") {
    $dockerVersion = docker --version 2>&1
    Write-Checkpoint "PASS" "Docker found: $dockerVersion"
} else {
    Write-Checkpoint "FAIL" "Docker not found. Please install Docker Desktop"
    $envValid = $false
}

# Check curl
if (Test-Command "curl.exe") {
    Write-Checkpoint "PASS" "curl.exe found"
} else {
    Write-Checkpoint "FAIL" "curl.exe not found"
    $envValid = $false
}

# Check wscat (optional)
if (Test-Command "wscat") {
    Write-Checkpoint "PASS" "wscat found (WebSocket testing available)"
} else {
    Write-Checkpoint "WARN" "wscat not found. Install with: npm install -g wscat"
}

if (-not $envValid) {
    Write-Host ""
    Write-Checkpoint "FAIL" "Environment validation failed. Please install missing dependencies."
    exit 1
}

Write-Host ""

# ============================================================================
# STAGE B: Start Database
# ============================================================================
if (-not $SkipDocker) {
    Write-Host "STAGE B: Start Database"
    Write-Host "-" * 80
    
    try {
        Write-Host "Starting PostgreSQL with docker-compose..."
        Push-Location $ProjectRoot
        docker-compose up -d postgres 2>&1 | Out-Null
        
        Write-Host "Waiting for PostgreSQL to be healthy..."
        $maxAttempts = 30
        for ($i = 1; $i -le $maxAttempts; $i++) {
            $health = docker-compose ps postgres | Select-String "healthy"
            if ($health) {
                Write-Checkpoint "PASS" "PostgreSQL is healthy"
                break
            }
            Start-Sleep -Seconds 1
        }
        
        if (-not $health) {
            Write-Checkpoint "FAIL" "PostgreSQL did not become healthy within timeout"
        }
    } catch {
        Write-Checkpoint "FAIL" "Failed to start PostgreSQL: $_"
    } finally {
        Pop-Location
    }
    Write-Host ""
} else {
    Write-Host "STAGE B: Skipped (SkipDocker flag set)"
    Write-Host ""
}

# ============================================================================
# STAGE C: Initialize Database
# ============================================================================
Write-Host "STAGE C: Initialize Database"
Write-Host "-" * 80

try {
    Write-Host "Running database initialization script..."
    Push-Location $ProjectRoot
    $result = python backend/database/init_db.py 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Checkpoint "PASS" "Database initialized successfully"
    } else {
        Write-Checkpoint "FAIL" "Database initialization failed"
        Write-Host "Error output: $result"
    }
} catch {
    Write-Checkpoint "FAIL" "Failed to run database initialization: $_"
} finally {
    Pop-Location
}
Write-Host ""

# ============================================================================
# STAGE D: Start FastAPI Server
# ============================================================================
Write-Host "STAGE D: Start FastAPI Server"
Write-Host "-" * 80

$backendProcess = $null
try {
    Write-Host "Starting uvicorn backend in background..."
    Push-Location $ProjectRoot
    
    # Start uvicorn in background
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = "python"
    $processInfo.Arguments = "-m uvicorn backend.main:app --host 0.0.0.0 --port $Port"
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.CreateNoWindow = $true
    
    $backendProcess = New-Object System.Diagnostics.Process
    $backendProcess.StartInfo = $processInfo
    $backendProcess.Start() | Out-Null
    
    Write-Host "Backend process started with PID: $($backendProcess.Id)"
    Write-Host "Waiting for backend to be healthy..."
    
    if (Invoke-HealthCheck -MaxAttempts 30) {
        Write-Checkpoint "PASS" "Backend server is healthy at $BaseUrl/health"
    } else {
        Write-Checkpoint "FAIL" "Backend server did not become healthy within timeout"
    }
} catch {
    Write-Checkpoint "FAIL" "Failed to start backend server: $_"
} finally {
    Pop-Location
}
Write-Host ""

# ============================================================================
# STAGE E: Verify API Security
# ============================================================================
Write-Host "STAGE E: Verify API Security"
Write-Host "-" * 80

# Test without API key (should fail)
try {
    Write-Host "Testing /api/sniffer/status WITHOUT API key (expect 401)..."
    $response = curl.exe -s -w "%{http_code}" "$BaseUrl/api/sniffer/status" -o /dev/null 2>$null
    if ($response -eq "401") {
        Write-Checkpoint "PASS" "API correctly rejected request without key (401)"
    } else {
        Write-Checkpoint "FAIL" "API returned $response instead of 401 (security issue)"
    }
} catch {
    Write-Checkpoint "FAIL" "Failed to test API security: $_"
}

# Test with API key (should succeed)
try {
    Write-Host "Testing /api/sniffer/status WITH API key (expect 200)..."
    $response = curl.exe -s -w "%{http_code}" "$BaseUrl/api/sniffer/status" -H "X-API-Key: $ApiKey" -o /dev/null 2>$null
    if ($response -eq "200") {
        Write-Checkpoint "PASS" "API correctly accepted request with key (200)"
    } else {
        Write-Checkpoint "FAIL" "API returned $response instead of 200 (authentication issue)"
    }
} catch {
    Write-Checkpoint "FAIL" "Failed to test API with key: $_"
}
Write-Host ""

# ============================================================================
# STAGE F: Interface Check
# ============================================================================
if (-not $SkipSniffer) {
    Write-Host "STAGE F: Interface Check"
    Write-Host "-" * 80
    
    try {
        Write-Host "Running interface discovery..."
        Push-Location $ProjectRoot
        $output = python backend/scripts/list_interfaces.py 2>&1
        Write-Host $output
        
        # Extract recommended interface from output
        if (-not $Interface) {
            # Try to extract recommended interface from output
            if ($output -match "Recommended interface for sniffing: (.+)") {
                $Interface = $matches[1].Trim()
                Write-Host "Auto-detected recommended interface: $Interface"
            } else {
                Write-Checkpoint "WARN" "Could not auto-detect interface. Please specify -Interface parameter"
                Write-Host "Common Windows interfaces: 'Wi-Fi', 'Ethernet', 'Local Area Connection'"
            }
        }
    } catch {
        Write-Checkpoint "FAIL" "Failed to run interface discovery: $_"
    } finally {
        Pop-Location
    }
    
    if ($Interface) {
        Write-Checkpoint "PASS" "Using interface: $Interface"
    } else {
        Write-Checkpoint "FAIL" "No interface specified. Use -Interface parameter"
    }
    Write-Host ""
} else {
    Write-Host "STAGE F: Skipped (SkipSniffer flag set)"
    Write-Host ""
}

# ============================================================================
# STAGE G: Start Sniffer
# ============================================================================
if (-not $SkipSniffer -and $Interface) {
    Write-Host "STAGE G: Start Sniffer"
    Write-Host "-" * 80
    
    try {
        Write-Host "Starting packet sniffer on interface: $Interface"
        $url = "$BaseUrl/api/sniffer/start?interface=$Interface&model_name=ensemble&min_packets=10&dry_run=false"
        $response = curl.exe -s -X POST $url -H "X-API-Key: $ApiKey" -H "Content-Type: application/json" 2>&1
        
        Write-Host "Response:"
        Write-Host $response
        
        # Check if start was successful
        if ($response -match '"success":\s*true' -or $response -match '"status":\s*"running"') {
            Write-Checkpoint "PASS" "Sniffer started successfully"
        } else {
            Write-Checkpoint "FAIL" "Sniffer failed to start"
        }
    } catch {
        Write-Checkpoint "FAIL" "Failed to start sniffer: $_"
    }
    Write-Host ""
} else {
    Write-Host "STAGE G: Skipped (SkipSniffer flag set or no interface)"
    Write-Host ""
}

# ============================================================================
# STAGE H: Verify Pipeline Running
# ============================================================================
if (-not $SkipSniffer -and $Interface) {
    Write-Host "STAGE H: Verify Pipeline Running"
    Write-Host "-" * 80
    
    try {
        Write-Host "Monitoring packet count for $RunDurationSec seconds..."
        $initialPacketCount = 0
        $finalPacketCount = 0
        
        # Get initial packet count
        $initialResponse = curl.exe -s "$BaseUrl/api/sniffer/status" -H "X-API-Key: $ApiKey" 2>&1
        if ($initialResponse -match '"packet_count":\s*(\d+)') {
            $initialPacketCount = [int]$matches[1]
        }
        
        # Monitor for specified duration
        for ($i = 1; $i -le $RunDurationSec; $i++) {
            Start-Sleep -Seconds 1
            $statusResponse = curl.exe -s "$BaseUrl/api/sniffer/status" -H "X-API-Key: $ApiKey" 2>&1
            
            if ($statusResponse -match '"packet_count":\s*(\d+)') {
                $currentCount = [int]$matches[1]
                Write-Host "  [$i/$RunDurationSec] Packet count: $currentCount"
            }
            
            if ($statusResponse -match '"is_running":\s*false') {
                Write-Host "  Pipeline stopped unexpectedly"
                break
            }
        }
        
        # Get final packet count
        $finalResponse = curl.exe -s "$BaseUrl/api/sniffer/status" -H "X-API-Key: $ApiKey" 2>&1
        if ($finalResponse -match '"packet_count":\s*(\d+)') {
            $finalPacketCount = [int]$matches[1]
        }
        
        $packetIncrease = $finalPacketCount - $initialPacketCount
        Write-Host "Initial packet count: $initialPacketCount"
        Write-Host "Final packet count: $finalPacketCount"
        Write-Host "Packet increase: $packetIncrease"
        
        if ($packetIncrease -gt 0) {
            Write-Checkpoint "PASS" "Pipeline is running and capturing packets"
        } else {
            Write-Checkpoint "WARN" "No packet increase detected (may be normal on quiet network)"
        }
    } catch {
        Write-Checkpoint "FAIL" "Failed to monitor pipeline: $_"
    }
    Write-Host ""
} else {
    Write-Host "STAGE H: Skipped (SkipSniffer flag set or no interface)"
    Write-Host ""
}

# ============================================================================
# STAGE I: Verify DB Insert (Alerts)
# ============================================================================
Write-Host "STAGE I: Verify Database Insert (Alerts)"
Write-Host "-" * 80

try {
    Write-Host "Fetching last 5 alerts from database..."
    $alertsResponse = curl.exe -s "$BaseUrl/api/alerts/" -H "X-API-Key: $ApiKey" 2>&1
    Write-Host "Response:"
    Write-Host $alertsResponse
    
    # Check if alerts exist
    if ($alertsResponse -match '"alert_id"' -or $alertsResponse -match '"id"') {
        Write-Checkpoint "PASS" "Alerts found in database"
    } else {
        Write-Checkpoint "WARN" "No alerts yet, try generating attack traffic"
        Write-Host "  Run: .\scripts\demo_attack_simulation.ps1"
    }
} catch {
    Write-Checkpoint "FAIL" "Failed to fetch alerts: $_"
}
Write-Host ""

# ============================================================================
# STAGE J: WebSocket Test Instructions
# ============================================================================
Write-Host "STAGE J: WebSocket Test Instructions"
Write-Host "-" * 80

Write-Host "To test real-time alert updates via WebSocket:"
Write-Host ""
Write-Host "  1. Install wscat (if not already installed):"
Write-Host "     npm install -g wscat"
Write-Host ""
Write-Host "  2. Connect to WebSocket:"
Write-Host "     wscat -c ws://localhost:$Port/ws"
Write-Host ""
Write-Host "  3. While connected, generate attack traffic to see real-time alerts"
Write-Host ""
Write-Checkpoint "INFO" "WebSocket endpoint: ws://localhost:$Port/ws"
Write-Host ""

# ============================================================================
# STAGE K: Stop Sniffer
# ============================================================================
if (-not $SkipSniffer -and $Interface) {
    Write-Host "STAGE K: Stop Sniffer"
    Write-Host "-" * 80
    
    try {
        Write-Host "Stopping packet sniffer..."
        $response = curl.exe -s -X POST "$BaseUrl/api/sniffer/stop" -H "X-API-Key: $ApiKey" 2>&1
        Write-Host "Response:"
        Write-Host $response
        
        if ($response -match '"success":\s*true' -or $response -match '"status":\s*"stopped"') {
            Write-Checkpoint "PASS" "Sniffer stopped successfully"
        } else {
            Write-Checkpoint "WARN" "Sniffer stop response unclear"
        }
    } catch {
        Write-Checkpoint "FAIL" "Failed to stop sniffer: $_"
    }
    Write-Host ""
} else {
    Write-Host "STAGE K: Skipped (SkipSniffer flag set or no interface)"
    Write-Host ""
}

# ============================================================================
# STAGE L: Shutdown Backend Process
# ============================================================================
Write-Host "STAGE L: Shutdown Backend Process"
Write-Host "-" * 80

if ($backendProcess -and -not $backendProcess.HasExited) {
    try {
        Write-Host "Stopping backend process (PID: $($backendProcess.Id))..."
        $backendProcess.Kill()
        $backendProcess.WaitForExit(5000)
        Write-Checkpoint "PASS" "Backend process stopped cleanly"
    } catch {
        Write-Checkpoint "FAIL" "Failed to stop backend process: $_"
    }
} else {
    Write-Checkpoint "INFO" "Backend process not running or already stopped"
}
Write-Host ""

# ============================================================================
# Summary
# ============================================================================
Write-Host "=" * 80
Write-Host "DEMO COMPLETED"
Write-Host "=" * 80
Write-Host ""
Write-Host "For attack simulation instructions, run:"
Write-Host "  .\scripts\demo_attack_simulation.ps1"
Write-Host ""
Write-Host "Expected screenshots for thesis defense:"
Write-Host "  1. Environment validation (all PASS)"
Write-Host "  2. Database initialization success"
Write-Host "  3. Backend health check (200 OK)"
Write-Host "  4. API security test (401 without key, 200 with key)"
Write-Host "  5. Interface discovery with recommended interface"
Write-Host "  6. Sniffer start success response"
Write-Host "  7. Packet count increasing over time"
Write-Host "  8. Alerts displayed from database"
Write-Host "  9. WebSocket connection command"
Write-Host "  10. Clean shutdown"
Write-Host ""
