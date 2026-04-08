#Requires -Version 5.1
# Start JARVIS Voice Server (FastAPI on 0.0.0.0:8000).
$ErrorActionPreference = 'Stop'

$JarvisRoot = Split-Path -Parent $PSScriptRoot
$VoiceDir = Join-Path $JarvisRoot 'voice'
$VenvPython = Join-Path $VoiceDir '.venv\Scripts\python.exe'
$Activate = Join-Path $VoiceDir '.venv\Scripts\Activate.ps1'

if (-not (Test-Path -LiteralPath $VoiceDir)) {
    throw "Voice directory not found: $VoiceDir"
}
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual env not found. Run: cd `"$VoiceDir`"; python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path -LiteralPath $Activate)) {
    throw "Activate script missing: $Activate"
}

Set-Location -LiteralPath $VoiceDir
. $Activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000
