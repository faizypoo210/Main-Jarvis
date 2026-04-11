#Requires -Version 5.1
# JARVIS master startup: governed stack first, supplemental surfaces last (idempotent).
$ErrorActionPreference = 'Stop'

# Give Windows services time to initialize
Start-Sleep -Seconds 5

$JarvisRoot = $PSScriptRoot
# Set User env JARVIS_LAN_IP to your Wi‑Fi IPv4 for phone access; never commit machine-specific IPs in the repo.
$LanIp = [Environment]::GetEnvironmentVariable('JARVIS_LAN_IP', 'User')
if ([string]::IsNullOrWhiteSpace($LanIp)) { $LanIp = $env:JARVIS_LAN_IP }
if ([string]::IsNullOrWhiteSpace($LanIp)) { $LanIp = '127.0.0.1' }
# Deprecated external UI (openclaw-mission-control). Not started unless explicitly enabled.
$LegacyMissionControlRoot = 'C:\projects\openclaw-mission-control'
$IncludeLegacyMissionControl = ($env:JARVIS_INCLUDE_MISSION_CONTROL -eq '1')

function Test-TcpListen([int]$Port) {
    return (@(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count -gt 0)
}

function Test-DockerContainerRunning([string]$Name) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        $out = docker inspect -f '{{.State.Running}}' $Name 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { return $false }
        return ($out.Trim() -eq 'true')
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Invoke-Step([string]$Message) {
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

Write-Host "JARVIS master start (repo: $JarvisRoot)" -ForegroundColor Green

# --- 1-2) Docker data plane ---
Invoke-Step "PostgreSQL (jarvis-postgres)"
if (Test-DockerContainerRunning 'jarvis-postgres') {
    Write-Host "Already running: jarvis-postgres"
} else {
    docker start jarvis-postgres 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "docker start jarvis-postgres failed (exit $LASTEXITCODE)." }
    Write-Host "Started: jarvis-postgres"
}

Invoke-Step "Redis (jarvis-redis)"
if (Test-DockerContainerRunning 'jarvis-redis') {
    Write-Host "Already running: jarvis-redis"
} else {
    docker start jarvis-redis 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "docker start jarvis-redis failed (exit $LASTEXITCODE)." }
    Write-Host "Started: jarvis-redis"
}

# --- 3) OpenClaw Gateway (agent runtime; executor/cLI depend on it) ---
Invoke-Step "OpenClaw Gateway"
if (Test-TcpListen 18789) {
    Write-Host "Gateway already listening on port 18789 (skip start script)."
} else {
    $gw = Join-Path $JarvisRoot 'scripts\03-start-gateway.ps1'
    & $gw
    if ($LASTEXITCODE -ne 0) { throw "03-start-gateway.ps1 failed (exit $LASTEXITCODE)." }
}

# Model lanes: local Ollama vs OpenClaw gateway (non-blocking; see docs/MODEL_LANES.md)
$laneVerify = Join-Path $JarvisRoot 'scripts\11-verify-model-lanes.ps1'
if (Test-Path -LiteralPath $laneVerify) {
    Invoke-Step "Model lane preflight (warnings only; does not block startup)"
    try {
        & $laneVerify -Startup
    } catch {
        Write-Host "[WARN] 11-verify-model-lanes.ps1 failed: $_" -ForegroundColor Yellow
    }
}

# --- 4) Control Plane (authoritative API) ---
Write-Host ""
Write-Host "Starting Jarvis Control Plane..." -ForegroundColor Cyan
$controlPlaneDir = Join-Path $JarvisRoot 'services\control-plane'
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$controlPlaneDir`"; `$env:PYTHONPATH='.'; uvicorn app.main:app --host 0.0.0.0 --port 8001" -WindowStyle Normal

Write-Host "Waiting for control plane to be ready..." -ForegroundColor Cyan
$cpReady = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $cpReady = $true; break }
    } catch { }
}
if (-not $cpReady) { Write-Host "WARNING: Control plane did not respond in time" -ForegroundColor Yellow }
else { Write-Host "Control plane ready." -ForegroundColor Green }

# --- 5) Command Center (primary operator UI) ---
Write-Host "Starting Jarvis Command Center..." -ForegroundColor Cyan
$commandCenterDir = Join-Path $JarvisRoot 'services\command-center'
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$commandCenterDir`"; npm run dev" -WindowStyle Minimized
Start-Sleep -Seconds 2

# --- 6) Voice Server ---
Write-Host "Starting Jarvis Voice Server..." -ForegroundColor Cyan
$voiceDir = Join-Path $JarvisRoot 'voice'
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$voiceDir`"; .\.venv\Scripts\Activate.ps1; uvicorn server:app --host 0.0.0.0 --port 8000" -WindowStyle Minimized
Start-Sleep -Seconds 2

# --- 7) Coordinator (Redis guard routing) ---
Write-Host "Starting Jarvis Coordinator..." -ForegroundColor Cyan
$coordDir = Join-Path $JarvisRoot 'coordinator'
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$coordDir`"; .\.venv\Scripts\Activate.ps1; python coordinator.py" -WindowStyle Minimized
Start-Sleep -Seconds 1

# --- 8) Executor (OpenClaw CLI worker) ---
Write-Host "Starting Jarvis Executor..." -ForegroundColor Cyan
$executorDir = Join-Path $JarvisRoot 'executor'
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$executorDir`"; .\.venv\Scripts\Activate.ps1; python -u executor.py" -WindowStyle Minimized
Start-Sleep -Seconds 2

# --- 9+) Supplemental only after core stack ---
Invoke-Step "LobsterBoard (supplemental dashboard)"
if (Test-TcpListen 8080) {
    Write-Host "LobsterBoard already listening on port 8080 (skip start script)."
} else {
    $lb = Join-Path $JarvisRoot 'scripts\04-start-lobsterboard.ps1'
    & $lb
    if ($LASTEXITCODE -ne 0) { throw "04-start-lobsterboard.ps1 failed (exit $LASTEXITCODE)." }
}

Invoke-Step "Ollama (local model)"
$ollamaScript = Join-Path $JarvisRoot 'scripts\05-start-ollama.ps1'
& $ollamaScript
if ($LASTEXITCODE -ne 0) { throw "05-start-ollama.ps1 failed (exit $LASTEXITCODE)." }

if ($IncludeLegacyMissionControl) {
    Invoke-Step "Legacy openclaw-mission-control (optional - deprecated)"
    $mcUp = (Test-TcpListen 3000) -and (Test-TcpListen 3001)
    if ($mcUp) {
        Write-Host "Legacy stack appears up (ports 3000 and 3001 listening)."
    } else {
        if (-not (Test-Path -LiteralPath $LegacyMissionControlRoot)) {
            throw "Legacy mission-control repo not found: $LegacyMissionControlRoot (unset JARVIS_INCLUDE_MISSION_CONTROL or clone the repo)."
        }
        Push-Location $LegacyMissionControlRoot
        try {
            docker compose up -d 2>&1 | Write-Host
            if ($LASTEXITCODE -ne 0) { throw "docker compose up -d failed in $LegacyMissionControlRoot (exit $LASTEXITCODE)." }
        } finally {
            Pop-Location
        }
        Write-Host "docker compose up -d completed."
    }
} else {
    Write-Host ""
    Write-Host "Legacy openclaw-mission-control: skipped. Primary UI: Command Center :5173; authority: Control Plane :8001." -ForegroundColor DarkGray
    Write-Host "To start deprecated 3000/3001 stack, set User env JARVIS_INCLUDE_MISSION_CONTROL=1." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "JARVIS is online." -ForegroundColor Green
Write-Host ""
Write-Host "Local URLs (core):" -ForegroundColor Cyan
Write-Host "  Command Center (primary UI): http://localhost:5173"
Write-Host "  Control Plane (authority):   http://localhost:8001"
Write-Host "  Voice Server:                http://localhost:8000"
Write-Host "  OpenClaw Gateway:            http://localhost:18789"
Write-Host "  Executor:                    running (background)"
Write-Host "  Coordinator:                 running (background)"
Write-Host ""
Write-Host "Local URLs (supplemental):" -ForegroundColor Cyan
Write-Host "  LobsterBoard:                http://localhost:8080"
Write-Host "  Ollama:                      http://localhost:11434"
if ($IncludeLegacyMissionControl) {
    Write-Host "  Legacy UI/API (deprecated):  http://localhost:3000 / http://localhost:3001"
}
Write-Host ""
Write-Host "LAN URLs (phone / same WiFi, $LanIp):" -ForegroundColor Cyan
Write-Host "  Command Center:   http://${LanIp}:5173"
Write-Host "  Control Plane:    http://${LanIp}:8001"
Write-Host "  Voice Server:     http://${LanIp}:8000"
Write-Host "  OpenClaw Gateway: http://${LanIp}:18789"
Write-Host "  LobsterBoard:     http://${LanIp}:8080"
Write-Host "  Ollama:           http://${LanIp}:11434"
Write-Host "  Executor/Coord:   background"
if ($IncludeLegacyMissionControl) {
    Write-Host "  Legacy 3000/3001: http://${LanIp}:3000 / http://${LanIp}:3001"
}

# System tray
$TrayDir = Join-Path $JarvisRoot 'tray'
$TrayPythonw = Join-Path $TrayDir '.venv\Scripts\pythonw.exe'
$TrayPyw = Join-Path $TrayDir 'tray.pyw'
Start-Process -FilePath $TrayPythonw -ArgumentList "`"$TrayPyw`"" -WorkingDirectory $TrayDir -WindowStyle Hidden

exit 0
