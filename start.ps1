# Root launcher shortcut for scripts\startup\start.ps1
$TargetScript = Join-Path $PSScriptRoot "scripts\startup\start.ps1"
if (Test-Path $TargetScript) {
    & $TargetScript @args
} else {
    Write-Error "Could not find $TargetScript"
}

