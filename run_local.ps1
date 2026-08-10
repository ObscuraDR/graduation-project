# Root launcher shortcut for scripts\startup\run_local.ps1
$TargetScript = Join-Path $PSScriptRoot "scripts\startup\run_local.ps1"
if (Test-Path $TargetScript) {
    & $TargetScript @args
} else {
    Write-Error "Could not find $TargetScript"
}

