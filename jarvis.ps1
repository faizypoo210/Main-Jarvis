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
# Legacy openclaw-mission-control (3000/3001) is deprecated — not started by this script. See deprecated/mission-control/.

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

function Test-HttpGetOk([string]$Uri, [int]$TimeoutSec = 3) {
    try {
        $r = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400)
    } catch {
        return $false
    }
}

function Write-JarvisLaunchStateFile {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)]$LaunchRecords
    )
    $dir = Join-Path $RepoRoot '.jarvis-local'
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $items = @()
    foreach ($r in $LaunchRecords) {
        if ($null -eq $r) { continue }
        $items += @{
            name      = $r.Name
            pid       = $r.Pid
            hostAlive = [bool]$r.HostAlive
            hostKind  = $r.HostKind
        }
    }
    $payload = @{
        generatedAt = (Get-Date).ToUniversalTime().ToString('o')
        schema      = 1
        repoRoot    = $RepoRoot
        launches    = $items
    }
    $path = Join-Path $dir 'launch-state.json'
    try {
        ($payload | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $path -Encoding UTF8
        Write-Host "Recorded launch PIDs -> $path" -ForegroundColor DarkGray
    } catch {
        Write-Host "[WARN] Could not write launch-state.json: $_" -ForegroundColor Yellow
    }
}

function Start-JarvisTrackedProcess {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)]$ArgumentList,
        [string]$WorkingDirectory = $null,
        [System.Diagnostics.ProcessWindowStyle]$WindowStyle = 'Minimized',
        [int]$SettleMs = 600,
        [ValidateSet('powershell-host', 'pythonw', 'other')][string]$HostKind = 'powershell-host'
    )
    $proc = $null
    try {
        $sp = @{
            FilePath     = $FilePath
            ArgumentList = $ArgumentList
            PassThru     = $true
            WindowStyle  = $WindowStyle
        }
        if ($WorkingDirectory) { $sp['WorkingDirectory'] = $WorkingDirectory }
        $proc = Start-Process @sp
    } catch {
        Write-Host "[$Name] Launch FAILED: $($_.Exception.Message)" -ForegroundColor Red
        return [pscustomobject]@{ Name = $Name; Pid = $null; HostAlive = $false; HostKind = $HostKind; Error = $_.Exception.Message }
    }
    if ($null -eq $proc) {
        Write-Host "[$Name] Launch FAILED: Start-Process returned null" -ForegroundColor Red
        return [pscustomobject]@{ Name = $Name; Pid = $null; HostAlive = $false; HostKind = $HostKind; Error = 'null process' }
    }
    Start-Sleep -Milliseconds $SettleMs
    $hostAlive = $false
    try {
        $null = Get-Process -Id $proc.Id -ErrorAction Stop
        $hostAlive = $true
    } catch {
        $hostAlive = $false
    }
    $statusTxt = if ($hostAlive) { 'host process running' } else { 'HOST EXITED IMMEDIATELY (or not visible)' }
    Write-Host ("[{0}] PID={1} - {2}" -f $Name, $proc.Id, $statusTxt) -ForegroundColor $(if ($hostAlive) { 'DarkGray' } else { 'Yellow' })
    return [pscustomobject]@{ Name = $Name; Pid = $proc.Id; HostAlive = $hostAlive; HostKind = $HostKind; Error = $null }
}

function Invoke-Step([string]$Message) {
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

Write-Host "JARVIS master start (repo: $JarvisRoot)" -ForegroundColor Green
$JarvisLaunchRecords = New-Object System.Collections.ArrayList

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

# --- 2b) Postgres readiness + Alembic (matches jarvis-start.bat; required when jarvis.ps1 is run alone) ---
Invoke-Step "Postgres readiness + Alembic"
$pgReady = $false
for ($i = 1; $i -le 10; $i++) {
    $null = docker exec jarvis-postgres pg_isready -U jarvis 2>&1
    if ($LASTEXITCODE -eq 0) { $pgReady = $true; break }
    Write-Host "Postgres not ready (attempt $i/10), waiting 3 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}
if (-not $pgReady) {
    Write-Host "ERROR: Postgres did not become ready in time (jarvis-postgres pg_isready)." -ForegroundColor Red
    exit 1
}
Write-Host "Postgres is ready." -ForegroundColor Green

$controlPlaneDir = Join-Path $JarvisRoot 'services\control-plane'
Push-Location -LiteralPath $controlPlaneDir
try {
    $venvPython = Join-Path $PWD '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        & $venvPython -m alembic upgrade head
    } else {
        & python -m alembic upgrade head
    }
    if ($LASTEXITCODE -ne 0) { throw "Alembic upgrade head failed (exit $LASTEXITCODE)." }
} finally {
    Pop-Location
}
Write-Host "Alembic: database schema at head." -ForegroundColor Green

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
$cpCmd = "cd `"$controlPlaneDir`"; `$env:PYTHONPATH='.'; uvicorn app.main:app --host 0.0.0.0 --port 8001"
$cpLaunch = Start-JarvisTrackedProcess -Name 'control-plane' -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-Command', $cpCmd) -WindowStyle Normal
[void]$JarvisLaunchRecords.Add($cpLaunch)

Write-Host "Waiting for control plane to be ready..." -ForegroundColor Cyan
$cpReady = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $cpReady = $true; break }
    } catch { }
}
if (-not $cpReady) {
    Write-Host "WARNING: Control plane did not respond to GET /health within the wait window (authority API not health-verified)." -ForegroundColor Yellow
} else {
    Write-Host "Control plane health-verified (GET http://localhost:8001/health)." -ForegroundColor Green
}

# --- 5) Command Center (primary operator UI) ---
Write-Host "Starting Jarvis Command Center..." -ForegroundColor Cyan
$commandCenterDir = Join-Path $JarvisRoot 'services\command-center'
$ccCmd = "cd `"$commandCenterDir`"; npm run dev"
$ccLaunch = Start-JarvisTrackedProcess -Name 'command-center' -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-Command', $ccCmd) -WindowStyle Minimized -WorkingDirectory $commandCenterDir
[void]$JarvisLaunchRecords.Add($ccLaunch)
Start-Sleep -Seconds 2
$ccHttpOk = $false
for ($i = 0; $i -lt 12; $i++) {
    if (Test-HttpGetOk 'http://localhost:5173/') { $ccHttpOk = $true; break }
    Start-Sleep -Seconds 1
}
if ($ccHttpOk) {
    Write-Host "Command Center responds over HTTP (dev server; not a formal health endpoint)." -ForegroundColor Green
} elseif (Test-TcpListen 5173) {
    Write-Host "Command Center: port 5173 is listening; HTTP not verified yet (may still be compiling)." -ForegroundColor Yellow
} else {
    Write-Host "Command Center: not listening on 5173 yet (process start attempted only)." -ForegroundColor Yellow
}

# --- 6) Voice Server ---
Write-Host "Starting Jarvis Voice Server..." -ForegroundColor Cyan
$voiceDir = Join-Path $JarvisRoot 'voice'
$voiceCmd = "cd `"$JarvisRoot`"; .\voice\.venv\Scripts\Activate.ps1; python -m uvicorn voice.server:app --host 0.0.0.0 --port 8000"
$voiceLaunch = Start-JarvisTrackedProcess -Name 'voice' -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-Command', $voiceCmd) -WindowStyle Minimized
[void]$JarvisLaunchRecords.Add($voiceLaunch)
Start-Sleep -Seconds 2
$voiceHttpOk = $false
for ($i = 0; $i -lt 10; $i++) {
    if (Test-HttpGetOk 'http://localhost:8000/') { $voiceHttpOk = $true; break }
    Start-Sleep -Seconds 1
}
if ($voiceHttpOk) {
    Write-Host "Voice server responds over HTTP (GET /)." -ForegroundColor Green
} elseif (Test-TcpListen 8000) {
    Write-Host "Voice server: port 8000 listening; HTTP not verified." -ForegroundColor Yellow
} else {
    Write-Host "Voice server: start attempted; not listening on 8000 yet." -ForegroundColor Yellow
}

# --- 7) Coordinator (Redis guard routing) ---
Write-Host "Starting Jarvis Coordinator..." -ForegroundColor Cyan
$coordDir = Join-Path $JarvisRoot 'coordinator'
$coordCmd = "cd `"$coordDir`"; .\.venv\Scripts\Activate.ps1; python coordinator.py"
$coordLaunch = Start-JarvisTrackedProcess -Name 'coordinator' -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-Command', $coordCmd) -WindowStyle Minimized
[void]$JarvisLaunchRecords.Add($coordLaunch)
Start-Sleep -Seconds 1

# --- 8) Executor (Ollama intent worker; legacy OpenClaw entrypoint is executor/executor.py, not started here) ---
Write-Host "Starting Jarvis Executor..." -ForegroundColor Cyan
$executorDir = Join-Path $JarvisRoot 'executor'
$execCmd = "cd `"$executorDir`"; .\.venv\Scripts\Activate.ps1; python -u worker.py"
$execLaunch = Start-JarvisTrackedProcess -Name 'executor' -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-Command', $execCmd) -WindowStyle Minimized
[void]$JarvisLaunchRecords.Add($execLaunch)
Start-Sleep -Seconds 2
Write-Host "Coordinator + Executor: PowerShell host windows launched (child python health not probed here)." -ForegroundColor DarkGray

# --- 9+) Supplemental only after core stack ---
Invoke-Step "LobsterBoard (supplemental dashboard)"
if (Test-TcpListen 8080) {
    Write-Host "LobsterBoard already listening on port 8080 (skip start script)."
} else {
    $lb = Join-Path $JarvisRoot 'scripts\04-start-lobsterboard.ps1'
    & $lb
    if ($LASTEXITCODE -ne 0) { throw "04-start-lobsterboard.ps1 failed (exit $LASTEXITCODE)." }
}
$lbListen = Test-TcpListen 8080

Invoke-Step "Ollama (local model)"
$ollamaScript = Join-Path $JarvisRoot 'scripts\05-start-ollama.ps1'
& $ollamaScript
if ($LASTEXITCODE -ne 0) { throw "05-start-ollama.ps1 failed (exit $LASTEXITCODE)." }
$ollamaListen = Test-TcpListen 11434

if ($env:JARVIS_INCLUDE_MISSION_CONTROL -eq '1') {
    Write-Host ""
    Write-Host "=== DEPRECATED: JARVIS_INCLUDE_MISSION_CONTROL=1 ===" -ForegroundColor Yellow
    Write-Host "Legacy Mission Control (openclaw-mission-control, ports 3000/3001) is NOT started by jarvis.ps1." -ForegroundColor Yellow
    Write-Host "Primary operator UI: Command Center (typically :5173). API authority: Control Plane (:8001). Stack: Coordinator + Executor + Voice + Gateway." -ForegroundColor Yellow
    $legacyMcDir = Join-Path $JarvisRoot 'deprecated\mission-control'
    Write-Host "Quarantined scripts and compose template (manual use only, do not extend):" -ForegroundColor DarkYellow
    Write-Host "  $legacyMcDir" -ForegroundColor DarkYellow
    Write-Host "Unset JARVIS_INCLUDE_MISSION_CONTROL to silence this reminder." -ForegroundColor DarkGray
} else {
    Write-Host ""
    Write-Host "Legacy openclaw-mission-control: unused (deprecated). See deprecated\mission-control\README.md." -ForegroundColor DarkGray
}

$gwListen = Test-TcpListen 18789
$gwHttpOk = $false
if ($gwListen) {
    if (Test-HttpGetOk 'http://127.0.0.1:18789/health') {
        $gwHttpOk = $true
    } elseif (Test-HttpGetOk 'http://127.0.0.1:18789/') {
        $gwHttpOk = $true
    }
}
if ($gwListen -and $gwHttpOk) {
    Write-Host "OpenClaw Gateway: listening + HTTP response (health or root)." -ForegroundColor Green
} elseif ($gwListen) {
    Write-Host "OpenClaw Gateway: listening on 18789; HTTP probe did not return OK (unverified beyond TCP)." -ForegroundColor Yellow
} else {
    Write-Host "OpenClaw Gateway: not listening on 18789." -ForegroundColor Yellow
}

# --- System tray (tracked; before summary so launch-state.json includes it) ---
$TrayDir = Join-Path $JarvisRoot 'tray'
$TrayPythonw = Join-Path $TrayDir '.venv\Scripts\pythonw.exe'
$TrayPyw = Join-Path $TrayDir 'tray.pyw'
if ((Test-Path -LiteralPath $TrayPythonw) -and (Test-Path -LiteralPath $TrayPyw)) {
    $trayLaunch = Start-JarvisTrackedProcess -Name 'tray' -FilePath $TrayPythonw -ArgumentList "`"$TrayPyw`"" -WorkingDirectory $TrayDir -WindowStyle Hidden -SettleMs 400 -HostKind 'pythonw'
    [void]$JarvisLaunchRecords.Add($trayLaunch)
} else {
    Write-Host "Tray: skipped (pythonw or tray.pyw missing) - $TrayDir" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Bring-up summary ===" -ForegroundColor Cyan
Write-Host "  Data plane:    PostgreSQL/Redis containers started (not HTTP-health-checked; use docker + ports)." -ForegroundColor Gray
Write-Host ("  Control plane: {0}" -f ($(if ($cpReady) { "HEALTHY - GET /health OK (host PID $($cpLaunch.Pid))" } else { "NOT HEALTH-VERIFIED - fix before trusting authority API (host PID $($cpLaunch.Pid))" }))) -ForegroundColor $(if ($cpReady) { 'Green' } else { 'Yellow' })
Write-Host ("  Gateway:       {0}" -f ($(if ($gwListen -and $gwHttpOk) { 'HEALTHY - HTTP OK' } elseif ($gwListen) { 'LISTENING - TCP only, HTTP unverified' } else { 'DOWN or not listening' }))) -ForegroundColor $(if ($gwListen -and $gwHttpOk) { 'Green' } elseif ($gwListen) { 'Yellow' } else { 'Yellow' })
Write-Host ("  Command Center:{0}" -f ($(if ($ccHttpOk) { " HTTP responds (dev UI); host PID $($ccLaunch.Pid)" } elseif (Test-TcpListen 5173) { " LISTENING only; host PID $($ccLaunch.Pid)" } else { " NOT LISTENING / HTTP unverified; host PID $($ccLaunch.Pid)" }))) -ForegroundColor $(if ($ccHttpOk) { 'Green' } elseif (Test-TcpListen 5173) { 'Yellow' } else { 'Yellow' })
Write-Host ("  Voice:         {0}" -f ($(if ($voiceHttpOk) { "HTTP responds on /; host PID $($voiceLaunch.Pid)" } elseif (Test-TcpListen 8000) { "LISTENING only; host PID $($voiceLaunch.Pid)" } else { "NOT LISTENING; host PID $($voiceLaunch.Pid)" }))) -ForegroundColor $(if ($voiceHttpOk) { 'Green' } elseif (Test-TcpListen 8000) { 'Yellow' } else { 'Yellow' })
Write-Host ("  Coordinator:   {0}" -f ($(if ($coordLaunch.HostAlive) { "Powershell host PID $($coordLaunch.Pid) (running - child python not probed here)" } else { "LAUNCH HOST MISSING - see [coordinator] line above" }))) -ForegroundColor $(if ($coordLaunch.HostAlive) { 'DarkGray' } else { 'Yellow' })
Write-Host ("  Executor:      {0}" -f ($(if ($execLaunch.HostAlive) { "Powershell host PID $($execLaunch.Pid) (running - child python not probed here)" } else { "LAUNCH HOST MISSING - see [executor] line above" }))) -ForegroundColor $(if ($execLaunch.HostAlive) { 'DarkGray' } else { 'Yellow' })
Write-Host ("  LobsterBoard:  {0}" -f ($(if ($lbListen) { "LISTENING (supplemental)" } else { "not listening on 8080" }))) -ForegroundColor $(if ($lbListen) { 'Gray' } else { 'Yellow' })
Write-Host ("  Ollama:        {0}" -f ($(if ($ollamaListen) { "LISTENING (optional local model)" } else { "OPTIONAL_DOWN / not on 11434" }))) -ForegroundColor $(if ($ollamaListen) { 'Gray' } else { 'Yellow' })
Write-Host "Core surfaces are not guaranteed healthy until verification passes; run scripts\07-verify-jarvis-stack.ps1 for a categorized check." -ForegroundColor DarkGray
Write-Host ""
Write-Host "=== Process launch (this run) ===" -ForegroundColor Cyan
Write-Host "  PowerShell hosts wrap services; uvicorn/npm/python are children - use ports/GET above for real health." -ForegroundColor DarkGray
foreach ($rec in $JarvisLaunchRecords) {
    if ($null -eq $rec) { continue }
    $pidStr = if ($rec.Pid) { "$($rec.Pid)" } else { '-' }
    $kind = $rec.HostKind
    $alive = if ($rec.HostAlive) { 'host present' } else { 'host missing / exited early' }
    $err = if ($rec.Error) { " err=$($rec.Error)" } else { '' }
    Write-Host ("  {0,-16} PID={1,-8} {2} ({3}){4}" -f $rec.Name, $pidStr, $alive, $kind, $err) -ForegroundColor $(if ($rec.HostAlive) { 'Gray' } else { 'Yellow' })
}
Write-Host ""
Write-Host "Bring-up initiated - see lines above for what is health-verified vs listening-only vs unverified." -ForegroundColor Green
Write-Host ""
Write-Host "Local URLs (core):" -ForegroundColor Cyan
Write-Host "  Command Center (primary UI): http://localhost:5173"
Write-Host "  Control Plane (authority):   http://localhost:8001"
Write-Host "  Voice Server:                http://localhost:8000"
Write-Host "  OpenClaw Gateway:            http://localhost:18789"
Write-Host "  Executor:                    PowerShell host PID $($execLaunch.Pid) (see ports/registry for work)"
Write-Host "  Coordinator:                 PowerShell host PID $($coordLaunch.Pid) (see Redis streams for work)"
Write-Host ""
Write-Host "Local URLs (supplemental):" -ForegroundColor Cyan
Write-Host "  LobsterBoard:                http://localhost:8080"
Write-Host "  Ollama:                      http://localhost:11434"
Write-Host ""
Write-Host "LAN URLs (phone / same WiFi, $LanIp):" -ForegroundColor Cyan
Write-Host "  Command Center:   http://${LanIp}:5173"
Write-Host "  Control Plane:    http://${LanIp}:8001"
Write-Host "  Voice Server:     http://${LanIp}:8000"
Write-Host "  OpenClaw Gateway: http://${LanIp}:18789"
Write-Host "  LobsterBoard:     http://${LanIp}:8080"
Write-Host "  Ollama:           http://${LanIp}:11434"
Write-Host "  Executor/Coord:   see PowerShell host PIDs in summary (watchdog supervises restarts - .jarvis-local\watchdog.log)"

Write-JarvisLaunchStateFile -RepoRoot $JarvisRoot -LaunchRecords $JarvisLaunchRecords

# --- Service watchdog (control plane, voice, executor, coordinator) ---
$watchdogScript = Join-Path $JarvisRoot 'scripts\watchdog.ps1'
if (Test-Path -LiteralPath $watchdogScript) {
    Write-Host ""
    Write-Host "Starting Jarvis service watchdog..." -ForegroundColor Cyan
    try {
        $wdProc = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', $watchdogScript,
            '-JarvisRoot', $JarvisRoot
        ) -WindowStyle Hidden -PassThru
        if ($wdProc) {
            Write-Host ("Watchdog process PID={0} - log: .jarvis-local\watchdog.log" -f $wdProc.Id) -ForegroundColor DarkGray
        } else {
            Write-Host "[WARN] Watchdog Start-Process returned null." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[WARN] Could not start watchdog: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] Watchdog script missing: $watchdogScript" -ForegroundColor Yellow
}

exit 0
