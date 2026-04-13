#Requires -Version 5.1
# Phase 7: Run jarvis.ps1, then classify readiness (HEALTHY / LISTENING / OPTIONAL_DOWN / DOWN).
# "READY" below means core gates passed for this script only — not supervised runtime health.
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$JarvisRoot = Split-Path -Parent $ScriptDir
$JarvisMain = Join-Path $JarvisRoot 'jarvis.ps1'

if (-not (Test-Path -LiteralPath $JarvisMain)) {
    throw "jarvis.ps1 not found at $JarvisMain"
}

Write-Host "Running $JarvisMain (bring-up; see script output for per-surface truth)..." -ForegroundColor Cyan
& $JarvisMain
if ($LASTEXITCODE -ne 0) {
    throw "jarvis.ps1 exited with code $LASTEXITCODE."
}

Start-Sleep -Seconds 3

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

function Test-HttpGetOk([string]$Uri, [int]$TimeoutSec = 4) {
    try {
        $r = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400)
    } catch {
        return $false
    }
}

function Test-JarvisProcessIdAlive {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    try {
        $null = Get-Process -Id $ProcessId -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Get-GatewayProbe {
    $listen = Test-TcpListen 18789
    if (-not $listen) {
        return @{ State = 'DOWN'; Detail = 'port 18789 not listening' }
    }
    if (Test-HttpGetOk 'http://127.0.0.1:18789/health') {
        return @{ State = 'HEALTHY'; Detail = 'TCP + GET /health OK' }
    }
    if (Test-HttpGetOk 'http://127.0.0.1:18789/') {
        return @{ State = 'HEALTHY'; Detail = 'TCP + GET / OK (no /health response)' }
    }
    return @{ State = 'LISTENING'; Detail = 'TCP only; HTTP not verified' }
}

$pg = Test-DockerContainerRunning 'jarvis-postgres'
$redis = Test-DockerContainerRunning 'jarvis-redis'

$cpHealthy = Test-HttpGetOk 'http://localhost:8001/health'
$ccListen = Test-TcpListen 5173
$ccHttp = $false
if ($ccListen) {
    $ccHttp = Test-HttpGetOk 'http://localhost:5173/'
}

$gw = Get-GatewayProbe

$voiceListen = Test-TcpListen 8000
$voiceHttp = $false
if ($voiceListen) {
    $voiceHttp = Test-HttpGetOk 'http://localhost:8000/'
}

$lbListen = Test-TcpListen 8080
$ollamaListen = Test-TcpListen 11434

$rows = @(
    @{
        Service = 'PostgreSQL (jarvis-postgres)'
        State   = $(if ($pg) { 'LISTENING' } else { 'DOWN' })
        Detail  = $(if ($pg) { 'docker container running' } else { 'container not running' })
    },
    @{
        Service = 'Redis (jarvis-redis)'
        State   = $(if ($redis) { 'LISTENING' } else { 'DOWN' })
        Detail  = $(if ($redis) { 'docker container running' } else { 'container not running' })
    },
    @{
        Service = 'Control Plane API'
        State   = $(if ($cpHealthy) { 'HEALTHY' } else { 'DOWN' })
        Detail  = $(if ($cpHealthy) { 'GET http://localhost:8001/health OK' } else { 'GET /health failed or unreachable' })
    },
    @{
        Service = 'OpenClaw Gateway'
        State   = $gw.State
        Detail  = $gw.Detail
    },
    @{
        Service = 'Command Center (Vite)'
        State   = $(if ($ccHttp) { 'HEALTHY' } elseif ($ccListen) { 'LISTENING' } else { 'DOWN' })
        Detail  = $(if ($ccHttp) { 'TCP + GET / OK (dev UI)' } elseif ($ccListen) { 'port 5173 only; HTTP not OK' } else { 'port 5173 not listening' })
    },
    @{
        Service = 'Voice Server'
        State   = $(if ($voiceHttp) { 'HEALTHY' } elseif ($voiceListen) { 'LISTENING' } else { 'DOWN' })
        Detail  = $(if ($voiceHttp) { 'TCP + GET / OK' } elseif ($voiceListen) { 'port 8000 only; HTTP not OK' } else { 'port 8000 not listening' })
    },
    @{
        Service = 'LobsterBoard (supplemental)'
        State   = $(if ($lbListen) { 'LISTENING' } else { 'OPTIONAL_DOWN' })
        Detail  = $(if ($lbListen) { 'port 8080' } else { 'not listening (optional)' })
    },
    @{
        Service = 'Ollama (optional)'
        State   = $(if ($ollamaListen) { 'LISTENING' } else { 'OPTIONAL_DOWN' })
        Detail  = $(if ($ollamaListen) { 'port 11434' } else { 'not listening (optional)' })
    }
)

Write-Host ""
Write-Host "========== Stack verification (categorized) ==========" -ForegroundColor Cyan

$coreFail =
    (-not $pg) -or
    (-not $redis) -or
    (-not $cpHealthy) -or
    ($gw.State -eq 'DOWN') -or
    (-not $ccHttp)

foreach ($r in $rows) {
    $line = "{0,-34} {1,-18} {2}" -f $r.Service, $r.State, $r.Detail
    $color = 'Gray'
    if ($r.State -eq 'HEALTHY') { $color = 'Green' }
    elseif ($r.State -eq 'LISTENING') { $color = 'Yellow' }
    elseif ($r.State -eq 'OPTIONAL_DOWN') { $color = 'DarkYellow' }
    elseif ($r.State -eq 'DOWN') { $color = 'Red' }

    Write-Host $line -ForegroundColor $color
}

$launchPath = Join-Path $JarvisRoot '.jarvis-local\launch-state.json'
Write-Host ""
Write-Host "========== Background hosts (cheap PID check) ==========" -ForegroundColor Cyan
Write-Host "  Not a supervisor - only compares last jarvis.ps1 PIDs to running processes (often powershell.exe hosting python/npm)." -ForegroundColor DarkGray
if (-not (Test-Path -LiteralPath $launchPath)) {
    Write-Host "  No launch-state.json - run repo-root jarvis.ps1 once to record host PIDs under .jarvis-local\" -ForegroundColor DarkGray
} else {
    try {
        $ls = Get-Content -LiteralPath $launchPath -Raw | ConvertFrom-Json
        if ($ls.repoRoot -and ($ls.repoRoot.TrimEnd('\') -ne $JarvisRoot.TrimEnd('\'))) {
            Write-Host "  [NOTE] launch-state repoRoot differs from this verify script - record may be stale." -ForegroundColor DarkYellow
        }
        $ageNote = ''
        try {
            $gen = [DateTimeOffset]::Parse($ls.generatedAt)
            $ageNote = " recorded $($gen.LocalDateTime.ToString('yyyy-MM-dd HH:mm'))"
        } catch { }
        Write-Host "  Source: $launchPath$ageNote" -ForegroundColor DarkGray
        $launches = @($ls.launches)
        foreach ($l in $launches) {
            $nm = [string]$l.name
            $pid = 0
            try { $pid = [int]$l.pid } catch { $pid = 0 }
            $kind = [string]$l.hostKind
            if ($pid -le 0) {
                Write-Host ("{0,-26} {1,-20} {2}" -f $nm, 'UNKNOWN', 'No PID in record') -ForegroundColor Yellow
                continue
            }
            $alive = Test-JarvisProcessIdAlive -ProcessId $pid
            if ($alive) {
                $st = 'PROCESS_PRESENT'
                $detail = "PID $pid still running ($kind - identity is generic; child workload not verified)"
                $color = 'Gray'
            } else {
                $st = 'PROCESS_GONE'
                $detail = "PID $pid not found (exited, rebooted, or stale record)"
                $color = 'Yellow'
            }
            Write-Host ("{0,-26} {1,-20} {2}" -f $nm, $st, $detail) -ForegroundColor $color
        }
    } catch {
        Write-Host "  [WARN] Could not read launch-state.json: $_" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Legacy Mission Control (3000/3001): not part of this stack - removed from verification." -ForegroundColor DarkGray

if ($gw.State -eq 'LISTENING') {
    Write-Host ""
    Write-Host "NOTE: Gateway is TCP-only / HTTP unverified - execution plane may still be misconfigured; fix gateway HTTP when possible." -ForegroundColor Yellow
}

if ($coreFail) {
    Write-Host ""
    Write-Host "NOT READY: core gate failed (containers, GET /health on control plane, gateway listen, or Command Center HTTP)." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "READY: data plane containers + control plane GET /health + gateway listening + Command Center HTTP." -ForegroundColor Green
Write-Host "Voice and optional services are reported above but do not fail this script." -ForegroundColor DarkGray
exit 0
