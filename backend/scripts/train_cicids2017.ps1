# CICIDS2017 Training Automation Script for Windows
# =================================================
# This script automates the preprocessing and training pipeline for CICIDS2017 dataset.
# It runs the preprocessing script to generate the processed CSV, then trains the model.

param(
    [Parameter(Mandatory=$true)]
    [string]$InputDir,
    
    [Parameter(Mandatory=$false)]
    [string]$OutputCsv = "backend/data/cicids2017_processed.csv",
    
    [Parameter(Mandatory=$false)]
    [string]$ModelType = "rf",
    
    [Parameter(Mandatory=$false)]
    [string]$OutputDir = "backend/models",
    
    [Parameter(Mandatory=$false)]
    [float]$TestSize = 0.2
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $BackendDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CICIDS2017 Training Pipeline" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Preprocessing
Write-Host "[Step 1/3] Preprocessing CICIDS2017 dataset..." -ForegroundColor Yellow
Write-Host "Input directory: $InputDir" -ForegroundColor Gray
Write-Host "Output CSV: $OutputCsv" -ForegroundColor Gray
Write-Host ""

$PreprocessScript = Join-Path $ScriptDir "preprocess_cicids2017.py"
$OutputCsvPath = Join-Path $ProjectRoot $OutputCsv

if (-not (Test-Path $PreprocessScript)) {
    Write-Host "ERROR: Preprocessing script not found at $PreprocessScript" -ForegroundColor Red
    exit 1
}

python $PreprocessScript --input-dir $InputDir --output $OutputCsvPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Preprocessing failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

Write-Host "Preprocessing completed successfully!" -ForegroundColor Green
Write-Host ""

# Verify output file exists
if (-not (Test-Path $OutputCsvPath)) {
    Write-Host "ERROR: Output CSV not found at $OutputCsvPath" -ForegroundColor Red
    exit 1
}

# Verify CSV has correct columns (20 features + Label)
Write-Host "[Verification] Checking output CSV structure..." -ForegroundColor Yellow
$CsvColumns = (Import-Csv -Path $OutputCsvPath | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name)
$ExpectedFeatures = @(
    "flow_duration", "total_fwd_packets", "total_bwd_packets", "total_fwd_bytes", 
    "total_bwd_bytes", "avg_packet_size", "packet_rate", "byte_rate", "syn_count", 
    "fin_count", "rst_count", "psh_count", "ack_count", "unique_dst_ports", 
    "inter_arrival_time_mean", "fwd_packet_rate", "bwd_packet_rate", "fwd_byte_rate", 
    "bwd_byte_rate", "packet_length_mean", "Label"
)

$MissingColumns = $ExpectedFeatures | Where-Object { $_ -notin $CsvColumns }
if ($MissingColumns) {
    Write-Host "WARNING: Missing expected columns: $($MissingColumns -join ', ')" -ForegroundColor Yellow
    Write-Host "Actual columns: $($CsvColumns -join ', ')" -ForegroundColor Gray
} else {
    Write-Host "CSV structure verified: 20 features + Label" -ForegroundColor Green
}
Write-Host ""

# Step 2: Training
Write-Host "[Step 2/3] Training ML model..." -ForegroundColor Yellow
Write-Host "Model type: $ModelType" -ForegroundColor Gray
Write-Host "Test size: $TestSize" -ForegroundColor Gray
Write-Host "Output directory: $OutputDir" -ForegroundColor Gray
Write-Host ""

$TrainScript = Join-Path $ProjectRoot "backend\ml\train_flow_model.py"
$OutputDirPath = Join-Path $ProjectRoot $OutputDir

if (-not (Test-Path $TrainScript)) {
    Write-Host "ERROR: Training script not found at $TrainScript" -ForegroundColor Red
    exit 1
}

python $TrainScript --data $OutputCsvPath --model $ModelType --test-size $TestSize --output-dir $OutputDirPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Training failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

Write-Host "Training completed successfully!" -ForegroundColor Green
Write-Host ""

# Step 3: Verification
Write-Host "[Step 3/3] Verifying artifacts..." -ForegroundColor Yellow

$RequiredArtifacts = @(
    "ensemble.pkl",
    "ensemble_scaler.pkl",
    "ensemble_encoder.pkl",
    "features.json"
)

$AllArtifactsExist = $true
foreach ($Artifact in $RequiredArtifacts) {
    $ArtifactPath = Join-Path $OutputDirPath $Artifact
    if (Test-Path $ArtifactPath) {
        Write-Host "  [OK] $Artifact" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $Artifact" -ForegroundColor Red
        $AllArtifactsExist = $false
    }
}

if (-not $AllArtifactsExist) {
    Write-Host "ERROR: Some artifacts are missing" -ForegroundColor Red
    exit 1
}

# Verify training report
$ReportPath = Join-Path $ProjectRoot "backend\reports\cicids2017_training_report.json"
if (Test-Path $ReportPath) {
    Write-Host "  [OK] Training report" -ForegroundColor Green
} else {
    Write-Host "  [MISSING] Training report" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Pipeline completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Artifacts saved to: $OutputDirPath" -ForegroundColor Gray
Write-Host "Training report: $ReportPath" -ForegroundColor Gray
Write-Host ""
