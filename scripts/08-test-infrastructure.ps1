#Requires -Version 5.1
# Phase 8: Infrastructure health — core (required for deployment report pass) vs extended (warn-only).
# Core: Postgres, Redis, Control Plane /health, OpenClaw gateway port + HTTP.
# Extended: Command Center dev server, LobsterBoard, Ollama, DashClaw site (machine may not run all).
$ErrorActionPreference = 'Continue'

$corePass = 0
$coreFail = 0
$extPass = 0
$extFail = 0

function Test-CoreStep {
    param([string]$Name, [scriptblock]$Probe)
    try {
        $ok = & $Probe
        if ($ok) {
            Write-Host "[PASS] [core] $Name" -ForegroundColor Green
            $script:corePass++
        } else {
            Write-Host "[FAIL] [core] $Name" -ForegroundColor Red
            $script:coreFail++
        }
    } catch {
        Write-Host "[FAIL] [core] $Name - $($_.Exception.Message)" -ForegroundColor Red
        $script:coreFail++
    }
}

function Test-ExtStep {
    param([string]$Name, [scriptblock]$Probe)
    try {
        $ok = & $Probe
        if ($ok) {
            Write-Host "[PASS] [extended] $Name" -ForegroundColor Green
            $script:extPass++
        } else {
            Write-Host "[WARN] [extended] $Name (non-blocking)" -ForegroundColor Yellow
            $script:extFail++
        }
    } catch {
        Write-Host "[WARN] [extended] $Name - $($_.Exception.Message) (non-blocking)" -ForegroundColor Yellow
        $script:extFail++
    }
}

Write-Host "=== 08-test-infrastructure (read-only) ===" -ForegroundColor Cyan
Write-Host "Core failures block the suite; extended failures are warnings only." -ForegroundColor DarkGray

# --- Core (5) ---
Test-CoreStep 'PostgreSQL (container + pg_isready)' {
    $r = docker inspect -f '{{.State.Running}}' jarvis-postgres 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $r.Trim() -ne 'true') { return $false }
    docker exec jarvis-postgres pg_isready -U jarvis -d jarvis_missions 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Test-CoreStep 'Redis (container + PING)' {
    $r = docker inspect -f '{{.State.Running}}' jarvis-redis 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $r.Trim() -ne 'true') { return $false }
    $out = docker exec jarvis-redis redis-cli PING 2>&1 | Out-String
    return ($out -match 'PONG')
}

Test-CoreStep 'Control Plane /health (8001)' {
    $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-CoreStep 'OpenClaw Gateway port 18789 listening' {
    return (@(Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue).Count -gt 0)
}

Test-CoreStep 'OpenClaw Gateway HTTP GET /' {
    $r = Invoke-WebRequest -Uri 'http://localhost:18789' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

# --- Extended (4) — optional local / third-party services ---
Test-ExtStep 'Command Center dev server (5173)' {
    $r = Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-ExtStep 'LobsterBoard HTTP GET /' {
    $r = Invoke-WebRequest -Uri 'http://localhost:8080' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-ExtStep 'Ollama HTTP GET /' {
    $r = Invoke-WebRequest -Uri 'http://localhost:11434' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-ExtStep 'DashClaw Vercel site' {
    $r = Invoke-WebRequest -Uri 'https://jarvis-dashclaw.vercel.app' -UseBasicParsing -TimeoutSec 25
    return ($r.StatusCode -eq 200)
}

$coreTotal = $corePass + $coreFail
$extTotal = $extPass + $extFail

Write-Host ""
Write-Host "Core summary:    $corePass/$coreTotal (required)" -ForegroundColor $(if ($coreFail -eq 0) { 'Green' } else { 'Red' })
Write-Host "Extended summary: $extPass/$extTotal (warnings only)" -ForegroundColor $(if ($extFail -eq 0) { 'Green' } else { 'Yellow' })
Write-Host "PHASE8 infrastructure_core $corePass $coreTotal"
Write-Host "PHASE8 infrastructure_extended $extPass $extTotal"

if ($coreFail -gt 0) { exit 1 }
exit 0
