#Requires -Version 5.1
# JARVIS master startup: bring up stack in order (idempotent; skips running services).
$ErrorActionPreference = 'Stop'

# Give Windows services time to initialize
Start-Sleep -Seconds 5

$JarvisRoot = $PSScriptRoot
$LanIp = '10.0.0.249'
$MissionControlRoot = 'C:\projects\openclaw-mission-control'

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

# 1) PostgreSQL
Invoke-Step "PostgreSQL (jarvis-postgres)"
if (Test-DockerContainerRunning 'jarvis-postgres') {
    Write-Host "Already running: jarvis-postgres"
} else {
    docker start jarvis-postgres 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "docker start jarvis-postgres failed (exit $LASTEXITCODE)." }
    Write-Host "Started: jarvis-postgres"
}

# 2) Redis
Invoke-Step "Redis (jarvis-redis)"
if (Test-DockerContainerRunning 'jarvis-redis') {
    Write-Host "Already running: jarvis-redis"
} else {
    docker start jarvis-redis 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "docker start jarvis-redis failed (exit $LASTEXITCODE)." }
    Write-Host "Started: jarvis-redis"
}

# 3) Mission Control (Docker Compose)
Invoke-Step "Mission Control (docker compose)"
$mcUp = (Test-TcpListen 3000) -and (Test-TcpListen 3001)
if ($mcUp) {
    Write-Host "Mission Control appears up (ports 3000 and 3001 listening)."
} else {
    if (-not (Test-Path -LiteralPath $MissionControlRoot)) {
        throw "Mission Control directory not found: $MissionControlRoot"
    }
    Push-Location $MissionControlRoot
    try {
        docker compose up -d 2>&1 | Write-Host
        if ($LASTEXITCODE -ne 0) { throw "docker compose up -d failed in $MissionControlRoot (exit $LASTEXITCODE)." }
    } finally {
        Pop-Location
    }
    Write-Host "docker compose up -d completed."
}

# 4) OpenClaw Gateway
Invoke-Step "OpenClaw Gateway"
if (Test-TcpListen 18789) {
    Write-Host "Gateway already listening on port 18789 (skip start script)."
} else {
    $gw = Join-Path $JarvisRoot 'scripts\03-start-gateway.ps1'
    & $gw
    if ($LASTEXITCODE -ne 0) { throw "03-start-gateway.ps1 failed (exit $LASTEXITCODE)." }
}

# 5) LobsterBoard
Invoke-Step "LobsterBoard"
if (Test-TcpListen 8080) {
    Write-Host "LobsterBoard already listening on port 8080 (skip start script)."
} else {
    $lb = Join-Path $JarvisRoot 'scripts\04-start-lobsterboard.ps1'
    & $lb
    if ($LASTEXITCODE -ne 0) { throw "04-start-lobsterboard.ps1 failed (exit $LASTEXITCODE)." }
}

# 6) Ollama
Invoke-Step "Ollama"
$ollamaScript = Join-Path $JarvisRoot 'scripts\05-start-ollama.ps1'
& $ollamaScript
if ($LASTEXITCODE -ne 0) { throw "05-start-ollama.ps1 failed (exit $LASTEXITCODE)." }

# Start Jarvis Control Plane
Write-Host "Starting Jarvis Control Plane..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd F:\Jarvis\services\control-plane; `$env:PYTHONPATH='.'; uvicorn app.main:app --host 0.0.0.0 --port 8001" -WindowStyle Normal

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

# Start Jarvis Command Center
Write-Host "Starting Jarvis Command Center..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd F:\Jarvis\services\command-center; npm run dev" -WindowStyle Minimized
Start-Sleep -Seconds 2

# Start Jarvis Voice Server
Write-Host "Starting Jarvis Voice Server..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd F:\Jarvis\voice; .\.venv\Scripts\Activate.ps1; uvicorn server:app --host 0.0.0.0 --port 8000" -WindowStyle Minimized
Start-Sleep -Seconds 2

# Event Coordinator
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd F:\Jarvis\coordinator; .\.venv\Scripts\Activate.ps1; python coordinator.py" -WindowStyle Minimized

# Start Jarvis Executor
Write-Host "Starting Jarvis Executor..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd F:\Jarvis\executor; .\.venv\Scripts\Activate.ps1; python -u executor.py" -WindowStyle Minimized
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "JARVIS is online." -ForegroundColor Green
Write-Host ""
Write-Host "Local URLs:" -ForegroundColor Cyan
Write-Host "  Mission Control UI:  http://localhost:3000"
Write-Host "  Mission Control API: http://localhost:3001"
Write-Host "  OpenClaw Gateway:    http://localhost:18789"
Write-Host "  LobsterBoard:        http://localhost:8080"
Write-Host "  Ollama:              http://localhost:11434"
Write-Host "  Command Center:      http://localhost:5173"
Write-Host "  Voice Server:        http://localhost:8000"
Write-Host "  Executor:            running (background)"
Write-Host ""
Write-Host "LAN URLs (phone / same WiFi, $LanIp):" -ForegroundColor Cyan
Write-Host "  Mission Control UI:  http://${LanIp}:3000"
Write-Host "  Mission Control API: http://${LanIp}:3001"
Write-Host "  OpenClaw Gateway:    http://${LanIp}:18789"
Write-Host "  LobsterBoard:        http://${LanIp}:8080"
Write-Host "  Ollama:              http://${LanIp}:11434"
Write-Host "  Command Center:      http://${LanIp}:5173"
Write-Host "  Voice Server:        http://${LanIp}:8000"
Write-Host "  Executor:            running (background)"

# System tray
$TrayDir = Join-Path $JarvisRoot 'tray'
$TrayPythonw = Join-Path $TrayDir '.venv\Scripts\pythonw.exe'
$TrayPyw = Join-Path $TrayDir 'tray.pyw'
Start-Process -FilePath $TrayPythonw -ArgumentList "`"$TrayPyw`"" -WorkingDirectory $TrayDir -WindowStyle Hidden

exit 0
