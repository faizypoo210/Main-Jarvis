#Requires -Version 5.1
# Start JARVIS Event Coordinator (Redis ↔ Control Plane ↔ DashClaw).
$ErrorActionPreference = 'Stop'

$JarvisRoot = Split-Path -Parent $PSScriptRoot
$CoordDir = Join-Path $JarvisRoot 'coordinator'
$VenvPython = Join-Path $CoordDir '.venv\Scripts\python.exe'
$Activate = Join-Path $CoordDir '.venv\Scripts\Activate.ps1'

if (-not (Test-Path -LiteralPath $CoordDir)) {
    throw "Coordinator directory not found: $CoordDir"
}
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual env not found. Run: cd `"$CoordDir`"; python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path -LiteralPath $Activate)) {
    throw "Activate script missing: $Activate"
}

Set-Location -LiteralPath $CoordDir
. $Activate
& $VenvPython coordinator.py
