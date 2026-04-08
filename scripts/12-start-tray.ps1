#Requires -Version 5.1
# Start JARVIS system tray (pythonw — no console window).
$ErrorActionPreference = 'Stop'

$JarvisRoot = Split-Path -Parent $PSScriptRoot
$TrayDir = Join-Path $JarvisRoot 'tray'
$VenvPythonw = Join-Path $TrayDir '.venv\Scripts\pythonw.exe'
$Activate = Join-Path $TrayDir '.venv\Scripts\Activate.ps1'
$TrayPyw = Join-Path $TrayDir 'tray.pyw'

if (-not (Test-Path -LiteralPath $TrayDir)) {
    throw "Tray directory not found: $TrayDir"
}
if (-not (Test-Path -LiteralPath $VenvPythonw)) {
    throw "Virtual env not found. Run: cd `"$TrayDir`"; python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path -LiteralPath $Activate)) {
    throw "Activate script missing: $Activate"
}
if (-not (Test-Path -LiteralPath $TrayPyw)) {
    throw "tray.pyw missing: $TrayPyw"
}

Set-Location -LiteralPath $TrayDir
. $Activate
& $VenvPythonw $TrayPyw
