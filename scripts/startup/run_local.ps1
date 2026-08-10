# ============================================================================
# Z-Sentinel IDS & Monitoring — Local Launcher Script (PowerShell)
# Kịch bản khởi chạy hệ thống cục bộ tự động hóa
# ============================================================================

$ErrorActionPreference = "Continue"
$ProjectRoot = (Get-Item "$PSScriptRoot\..\..").FullName
if (-not (Test-Path "$ProjectRoot\README.md")) { $ProjectRoot = (Get-Location).ProviderPath }
Set-Location $ProjectRoot

function Write-Step { param([string]$msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-WARN { param([string]$msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-FAIL { param([string]$msg) Write-Host "  [ERR] $msg" -ForegroundColor Red }

# 1. Xác thực môi trường và file cấu hình
Write-Step "BUOC 1: Kiem tra moi truong he thong..."

# Kiểm tra Python
$HasPython = $false
try {
    $null = Get-Command python -ErrorAction Stop
    $pyVer = python --version 2>&1
    Write-OK "Tim thay Python: $pyVer"
    $HasPython = $true
} catch {
    Write-FAIL "Khong tim thay Python. Vui long cai dat Python 3.8+ va them vao PATH."
}

# Kiểm tra Docker
$HasDocker = $false
try {
    $null = Get-Command docker -ErrorAction Stop
    $dockerVer = docker --version 2>&1
    Write-OK "Tim thay Docker: $dockerVer"
    $HasDocker = $true
} catch {
    Write-WARN "Khong tim thay Docker. Ban can tu chay PostgreSQL ngoai Docker."
}

# Kiểm tra Node.js và npm
$HasNode = $false
try {
    $null = Get-Command node -ErrorAction Stop
    $null = Get-Command npm -ErrorAction Stop
    $nodeVer = node -v
    Write-OK "Tim thay Node.js: $nodeVer va npm"
    $HasNode = $true
} catch {
    Write-FAIL "Khong tim thay Node.js hoac npm. Vui long cai dat Node.js de chay Frontend."
}

# Sao chép file cấu hình .env nếu chưa có
if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-WARN "Khong tim thay file .env. Dang tu dong sao chep tu .env.example..."
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
    Write-OK "Da tao file .env."
} else {
    Write-OK "File .env da san sang."
}

# Phân tích cài đặt từ file .env
$PostgresPort = 5433
$ApiKey = "changeme-set-API_KEY-in-env"
if (Test-Path "$ProjectRoot\.env") {
    $envContent = Get-Content "$ProjectRoot\.env"
    foreach ($line in $envContent) {
        if ($line -match "^POSTGRES_PORT=(\d+)") {
            $PostgresPort = [int]$matches[1]
        }
        if ($line -match "^API_KEY=(.+)") {
            $ApiKey = $matches[1].Trim()
        }
    }
}

# Phát hiện môi trường ảo
$VenvPath = ""
if (Test-Path "$ProjectRoot\.venv\Scripts\Activate.ps1") {
    $VenvPath = "$ProjectRoot\.venv\Scripts\Activate.ps1"
} elseif (Test-Path "$ProjectRoot\venv\Scripts\Activate.ps1") {
    $VenvPath = "$ProjectRoot\venv\Scripts\Activate.ps1"
}

if (-not $VenvPath -and $HasPython) {
    Write-WARN "Khong tim thay virtualenv. Dang tao .venv..."
    python -m venv "$ProjectRoot\.venv"
    if (Test-Path "$ProjectRoot\.venv\Scripts\Activate.ps1") {
        $VenvPath = "$ProjectRoot\.venv\Scripts\Activate.ps1"
        Write-OK "Da tao .venv."
    } else {
        Write-FAIL "Khong the tao virtualenv."
    }
} else {
    Write-OK "Duong dan moi truong ao: $VenvPath"
}

# 2. Cài đặt các thư viện phụ thuộc
Write-Step "BUOC 2: Cai dat thu vien phu thuoc..."

if ($VenvPath) {
    Write-Host "Dang cai dat thu vien backend..." -ForegroundColor Yellow
    . $VenvPath
    python -m pip install --upgrade pip
    pip install -r "$ProjectRoot\requirements.txt"
    Write-OK "Da cai dat thu vien backend."
}

if ($HasNode) {
    if (-not (Test-Path "$ProjectRoot\frontend\node_modules")) {
        Write-Host "Dang chay npm install cho frontend..." -ForegroundColor Yellow
        Push-Location "$ProjectRoot\frontend"
        npm install
        Pop-Location
        Write-OK "Da cai dat thu vien frontend."
    } else {
        Write-OK "Thu vien frontend da san sang."
    }
}

# 3. Quản lý cơ sở dữ liệu
function Start-Database {
    Write-Step "BUOC 3: Khoi dong co so du lieu..."
    if ($HasDocker) {
        Write-Host "Dang chay docker-compose up..." -ForegroundColor Yellow
        Push-Location $ProjectRoot
        docker-compose up -d postgres
        Pop-Location
        
        Write-Host "Dang kiem tra PostgreSQL..." -ForegroundColor Yellow
        $dbHealthy = $false
        for ($i = 1; $i -le 10; $i++) {
            Push-Location $ProjectRoot
            $status = docker-compose ps postgres
            Pop-Location
            if ($status -like "*healthy*") {
                $dbHealthy = $true
                break
            }
            Start-Sleep -Seconds 2
        }
        if ($dbHealthy) {
            Write-OK "PostgreSQL dang chay (healthy)."
        } else {
            Write-WARN "Chua check thay healthy nhung se tiep tuc..."
        }
    } else {
        Write-WARN "Bo qua Docker, hay chac chan Postgres dang chay o cong $PostgresPort."
    }
}

# 4. Migration và Seed data
function Init-DatabaseAndModels {
    Write-Step "BUOC 4: Khoi tao du lieu va models..."
    if ($VenvPath) {
        . $VenvPath
        Write-Host "Dang chay database migrations (Alembic)..." -ForegroundColor Yellow
        alembic upgrade head
        
        Write-Host "Dang seed du lieu..." -ForegroundColor Yellow
        python "$ProjectRoot\backend\database\init_db.py"
        
        if (-not (Test-Path "$ProjectRoot\backend\models\ensemble.pkl") -and -not (Test-Path "$ProjectRoot\data\models\ensemble.pkl")) {
            Write-WARN "Dang tao ML dummy models..."
            python "$ProjectRoot\ai\create_dummy_models.py"
            Write-OK "Da tao dummy models."
        } else {
            Write-OK "ML models da san sang."
        }
    } else {
        Write-FAIL "Khong the migration do thieu venv."
    }
}

# Chạy tuần tự DB
Start-Database
Init-DatabaseAndModels

# 5. Menu khởi chạy
while ($true) {
    Write-Host "`n===========================================================" -ForegroundColor Cyan
    Write-Host "              Z-SENTINEL IDS - BANG DIEU KHIEN RUN LOCAL    " -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host " [1] Chay TOAN BO he thong (Backend + Frontend + Agent)" -ForegroundColor Green
    Write-Host " [2] Chi chay FastAPI Backend" -ForegroundColor White
    Write-Host " [3] Chi chay React Frontend Dashboard" -ForegroundColor White
    Write-Host " [4] Chi chay Local Security Agent" -ForegroundColor White
    Write-Host " [5] Chi chay PostgreSQL Database" -ForegroundColor White
    Write-Host " [6] Tat toan bo cac dich vu dang chay" -ForegroundColor Yellow
    Write-Host " [7] Thoat" -ForegroundColor Red
    Write-Host "===========================================================" -ForegroundColor Cyan
    
    $choice = Read-Host "Nhap lua chon cua ban (1-7)"
    
    switch ($choice) {
        "1" {
            Write-Host "`nDang mo cac cua so Terminal moi..." -ForegroundColor Yellow
            
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- FASTAPI BACKEND SERVER ---' -ForegroundColor Green; . '$VenvPath'; python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" -WorkingDirectory $ProjectRoot -WindowStyle Normal
            Write-OK "Da mo Backend."
            
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- REACT FRONTEND DASHBOARD ---' -ForegroundColor Green; npm run dev" -WorkingDirectory "$ProjectRoot\frontend" -WindowStyle Normal
            Write-OK "Da mo Frontend."
            
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- SECURITY AGENT ---' -ForegroundColor Green; . '$VenvPath'; `$env:AGENT_API_KEY='$ApiKey'; `$env:IDS_API_URL='http://localhost:8000/api/servers'; python backend/scripts/agent.py" -WorkingDirectory $ProjectRoot -WindowStyle Normal
            Write-OK "Da mo Agent."
            
            Write-Host "`n-> Xem dashboard tai: http://localhost:3000" -ForegroundColor Cyan
            Write-Host "-> Xem API docs tai: http://localhost:8000/docs" -ForegroundColor Cyan
        }
        "2" {
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- FASTAPI BACKEND SERVER ---' -ForegroundColor Green; . '$VenvPath'; python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" -WorkingDirectory $ProjectRoot -WindowStyle Normal
        }
        "3" {
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- REACT FRONTEND DASHBOARD ---' -ForegroundColor Green; npm run dev" -WorkingDirectory "$ProjectRoot\frontend" -WindowStyle Normal
        }
        "4" {
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- SECURITY AGENT ---' -ForegroundColor Green; . '$VenvPath'; `$env:AGENT_API_KEY='$ApiKey'; `$env:IDS_API_URL='http://localhost:8000/api/servers'; python backend/scripts/agent.py" -WorkingDirectory $ProjectRoot -WindowStyle Normal
        }
        "5" {
            Start-Database
        }
        "6" {
            Write-Host "`nDang tat cac tien trinh..." -ForegroundColor Yellow
            Get-Process | Where-Object { $_.ProcessName -eq "python" -or $_.CommandLine -like "*uvicorn*" } | ForEach-Object {
                try { Stop-Process -Id $_.Id -Force; Write-OK "Da tat Python (PID: $($_.Id))" } catch {}
            }
            Get-Process | Where-Object { $_.ProcessName -eq "node" } | ForEach-Object {
                try { Stop-Process -Id $_.Id -Force; Write-OK "Da tat Node (PID: $($_.Id))" } catch {}
            }
            if ($HasDocker) {
                Push-Location $ProjectRoot
                docker-compose down
                Pop-Location
                Write-OK "Da dung Docker Postgres."
            }
            Write-OK "Da don dep."
        }
        "7" {
            break
        }
    }
}
