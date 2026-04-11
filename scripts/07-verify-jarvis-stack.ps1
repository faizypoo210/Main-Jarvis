#Requires -Version 5.1
# Phase 7: Run jarvis.ps1 and verify core services; Ollama is optional (warning only).
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$JarvisRoot = Split-Path -Parent $ScriptDir
$JarvisMain = Join-Path $JarvisRoot 'jarvis.ps1'

if (-not (Test-Path -LiteralPath $JarvisMain)) {
    throw "jarvis.ps1 not found at $JarvisMain"
}

Write-Host "Running $JarvisMain ..." -ForegroundColor Cyan
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

$IncludeMc = ($env:JARVIS_INCLUDE_MISSION_CONTROL -eq '1')

$rows = @(
    @{ Service = 'PostgreSQL (jarvis-postgres)'; Port = 5432; Check = { Test-DockerContainerRunning 'jarvis-postgres' } },
    @{ Service = 'Redis (jarvis-redis)';       Port = 6379; Check = { Test-DockerContainerRunning 'jarvis-redis' } },
    @{ Service = 'Control Plane API';          Port = 8001; Check = { Test-TcpListen 8001 } },
    @{ Service = 'Command Center (Vite)';      Port = 5173; Check = { Test-TcpListen 5173 } },
    @{ Service = 'Voice Server';               Port = 8000; Check = { Test-TcpListen 8000 } },
    @{ Service = 'OpenClaw Gateway';           Port = 18789; Check = { Test-TcpListen 18789 } },
    @{ Service = 'LobsterBoard';              Port = 8080; Check = { Test-TcpListen 8080 } },
    @{ Service = 'Ollama (optional)';         Port = 11434; Check = { Test-TcpListen 11434 }; Optional = $true }
)

if ($IncludeMc) {
    $rows += @(
        @{ Service = 'Mission Control UI (legacy)'; Port = 3000; Check = { Test-TcpListen 3000 } },
        @{ Service = 'Mission Control API (legacy)'; Port = 3001; Check = { Test-TcpListen 3001 } }
    )
}

Write-Host ""
Write-Host "========== Stack status ==========" -ForegroundColor Cyan
$coreOk = $true
foreach ($r in $rows) {
    $ok = & $r.Check
    $st = if ($ok) { 'UP' } else { 'DOWN' }
    if (-not $ok -and -not $r.Optional) { $coreOk = $false }
    if ($r.Optional -and -not $ok) {
        Write-Host ("{0,-32} Port={1,-6} {2} (optional)" -f $r.Service, $r.Port, $st) -ForegroundColor Yellow
    } else {
        $color = if ($ok) { 'Green' } else { 'Red' }
        Write-Host ("{0,-32} Port={1,-6} {2}" -f $r.Service, $r.Port, $st) -ForegroundColor $color
    }
}

if (-not $coreOk) {
    Write-Host ""
    Write-Host "One or more core services are not running." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "All core services verified." -ForegroundColor Green
exit 0
