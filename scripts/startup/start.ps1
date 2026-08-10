# ============================================================================
#  Z-Sentinel IDS — Start Script
#  Cách dùng: Click chuột phải → "Run with PowerShell"
#  Hoặc trong terminal: .\start.ps1
#  Tùy chọn:
#    .\start.ps1          → chạy Backend + Frontend
#    .\start.ps1 -Agent   → chạy thêm Agent
#    .\start.ps1 -Stop    → dừng toàn bộ
# ============================================================================

param(
    [switch]$Agent,   # Bật để chạy thêm Agent
    [switch]$Stop     # Dừng toàn bộ services
)

$ProjectRoot = (Get-Item "$PSScriptRoot\..\..").FullName
if (-not (Test-Path "$ProjectRoot\README.md")) { $ProjectRoot = (Get-Location).ProviderPath }
Set-Location $ProjectRoot

$VenvActivate = "$ProjectRoot\.venv\Scripts\Activate.ps1"
$ApiKey       = "changeme-set-API_KEY-in-env"

function Write-Header {
    Clear-Host
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "           Z-SENTINEL IDS — LAUNCHER                       " -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-OK   { param($msg) Write-Host "  [OK]  $msg" -ForegroundColor Green }
function Write-WARN { param($msg) Write-Host "  [!!]  $msg" -ForegroundColor Yellow }
function Write-FAIL { param($msg) Write-Host "  [ERR] $msg" -ForegroundColor Red }
function Write-INFO { param($msg) Write-Host "  [>>]  $msg" -ForegroundColor Cyan }

# ── STOP ─────────────────────────────────────────────────────────────────────
if ($Stop) {
    Write-Header
    Write-INFO "Dang dung tat ca services..."

    # Dừng Python (Backend + Agent)
    Get-Process -Name "python" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-OK "Da dung Backend / Agent (Python)"

    # Dừng Node (Frontend)
    Get-Process -Name "node" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-OK "Da dung Frontend (Node)"

    # Dừng PostgreSQL Docker
    $dockerRunning = $false
    try {
        $null = docker info 2>$null
        $dockerRunning = $true
    } catch {}

    if ($dockerRunning) {
        Push-Location $ProjectRoot
        docker-compose down 2>$null
        Pop-Location
        Write-OK "Da dung PostgreSQL (Docker)"
    }

    Write-Host ""
    Write-Host "  Tat ca services da duoc dung." -ForegroundColor Green
    Write-Host ""
    pause
    exit 0
}

# ── START ─────────────────────────────────────────────────────────────────────
Write-Header

# ── Bước 1: Kiểm tra môi trường ───────────────────────────────────────────────
Write-INFO "Buoc 1: Kiem tra moi truong..."

# Python
try {
    $pyVer = python --version 2>&1
    Write-OK "Python: $pyVer"
} catch {
    Write-FAIL "Khong tim thay Python. Cai tai: https://www.python.org/downloads/"
    pause; exit 1
}

# Node
try {
    $nodeVer = node -v 2>&1
    Write-OK "Node.js: $nodeVer"
} catch {
    Write-FAIL "Khong tim thay Node.js. Cai tai: https://nodejs.org/"
    pause; exit 1
}

# Docker
$HasDocker = $false
try {
    $null = docker info 2>$null
    $HasDocker = $true
    Write-OK "Docker Desktop: Running"
} catch {
    Write-WARN "Docker Desktop chua chay. Hay mo Docker Desktop truoc!"
    Write-WARN "Neu khong co Docker, hay cai PostgreSQL thu cong."
}

# venv
if (-not (Test-Path $VenvActivate)) {
    Write-FAIL "Khong tim thay .venv. Chay lenh sau de tao:"
    Write-Host "       py -3.13 -m venv .venv" -ForegroundColor Yellow
    Write-Host "       .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "       pip install -r requirements.txt" -ForegroundColor Yellow
    Write-Host "       pip install shap==0.52.0 --only-binary=:all:" -ForegroundColor Yellow
    pause; exit 1
}
Write-OK "Virtual environment: .venv"

# node_modules
if (-not (Test-Path "$ProjectRoot\frontend\node_modules")) {
    Write-WARN "Chua co node_modules. Dang chay npm install..."
    Push-Location "$ProjectRoot\frontend"
    npm install --silent
    Pop-Location
    Write-OK "Da cai xong node_modules"
}
Write-Host ""

# ── Bước 2: Khởi động PostgreSQL ─────────────────────────────────────────────
Write-INFO "Buoc 2: Khoi dong PostgreSQL..."

if ($HasDocker) {
    Push-Location $ProjectRoot
    $pgStatus = docker-compose ps postgres 2>$null | Select-String "healthy|running"
    if ($pgStatus) {
        Write-OK "PostgreSQL da chay san."
    } else {
        docker-compose up -d postgres 2>$null
        Write-INFO "Dang cho PostgreSQL san sang..."
        $waited = 0
        do {
            Start-Sleep -Seconds 2
            $waited += 2
            $pgStatus = docker-compose ps postgres 2>$null | Select-String "healthy|Up"
        } while (-not $pgStatus -and $waited -lt 30)

        if ($pgStatus) {
            Write-OK "PostgreSQL da khoi dong thanh cong."
        } else {
            Write-WARN "PostgreSQL co the chua san sang. Kiem tra Docker Desktop."
        }
    }
    Pop-Location
} else {
    Write-WARN "Bo qua Docker — gia su PostgreSQL dang chay local."
}
Write-Host ""

# ── Bước 3: Khởi động Backend ────────────────────────────────────────────────
Write-INFO "Buoc 3: Mo cua so Backend (FastAPI)..."

$backendCmd = ". '$VenvActivate'; python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Write-Host '=== BACKEND - FastAPI ===' -ForegroundColor Green; $backendCmd" `
    -WorkingDirectory $ProjectRoot -WindowStyle Normal

Write-OK "Da mo Backend terminal."
Write-INFO "Dang cho Backend khoi dong (5s)..."
Start-Sleep -Seconds 5

# Kiểm tra backend có chạy không
try {
    $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
    if ($health.StatusCode -eq 200) {
        Write-OK "Backend dang chay tai: http://localhost:8000"
    }
} catch {
    Write-WARN "Backend chua phan hoi — co the dang khoi dong. Kiem tra cua so Backend."
}
Write-Host ""

# ── Bước 4: Khởi động Frontend ───────────────────────────────────────────────
Write-INFO "Buoc 4: Mo cua so Frontend (React)..."

Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Write-Host '=== FRONTEND - React Dashboard ===' -ForegroundColor Cyan; npm run dev" `
    -WorkingDirectory "$ProjectRoot\frontend" -WindowStyle Normal

Write-OK "Da mo Frontend terminal."
Write-Host ""

# ── Bước 5: Agent (tùy chọn) ─────────────────────────────────────────────────
if ($Agent) {
    Write-INFO "Buoc 5: Mo cua so Agent..."

    $agentCmd = ". '$VenvActivate'; `$env:IDS_API_URL='http://localhost:8000/api/servers'; `$env:AGENT_API_KEY='$ApiKey'; python backend/scripts/agent.py"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
        "Write-Host '=== AGENT - Security Monitor ===' -ForegroundColor Yellow; $agentCmd" `
        -WorkingDirectory $ProjectRoot -WindowStyle Normal

    Write-OK "Da mo Agent terminal."
    Write-Host ""
}

# ── Tóm tắt ──────────────────────────────────────────────────────────────────
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  He thong dang khoi dong...                               " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard  : http://localhost:3000" -ForegroundColor Cyan
Write-Host "  API Docs   : http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Dang nhap  : admin / admin123" -ForegroundColor Cyan
Write-Host ""
Write-Host "  De dung tat ca: .\start.ps1 -Stop" -ForegroundColor Yellow
if (-not $Agent) {
    Write-Host "  De chay them Agent: .\start.ps1 -Agent" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green

# Mở browser sau 5 giây
Write-INFO "Tu dong mo browser sau 5 giay..."
Start-Sleep -Seconds 5
Start-Process "http://localhost:3000"
