#Requires -Version 5.1
# Thin wrapper: workspace governance manifest audit (repo-native, no network).
$ErrorActionPreference = 'Continue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Audit = Join-Path $ScriptDir '11-audit-workspace-governance.ps1'

Write-Host "=== 08-smoke-workspace-governance (delegates to 11-audit) ===" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $Audit)) {
    Write-Host "[FAIL] Missing $Audit" -ForegroundColor Red
    Write-Host "PHASE8 workspace_governance 0 1"
    exit 1
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Audit 2>&1 | Write-Host
$code = $LASTEXITCODE
if ($null -eq $code) { $code = -1 }

if ($code -eq 0) {
    Write-Host "PHASE8 workspace_governance 1 1"
    exit 0
}
Write-Host "PHASE8 workspace_governance 0 1"
exit 1
