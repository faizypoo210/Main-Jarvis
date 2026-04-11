#Requires -Version 5.1
# Phase 8: Read-only infrastructure health checks (9 probes); exits 0 only if all pass.
$ErrorActionPreference = 'Continue'

$pass = 0
$fail = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Probe)
    try {
        $ok = & $Probe
        if ($ok) {
            Write-Host "[PASS] $Name"
            $script:pass++
        } else {
            Write-Host "[FAIL] $Name (returned false)"
            $script:fail++
        }
    } catch {
        Write-Host "[FAIL] $Name - $($_.Exception.Message)"
        $script:fail++
    }
}

Write-Host "=== 08-test-infrastructure (read-only) ===" -ForegroundColor Cyan

Test-Step 'PostgreSQL (container + pg_isready)' {
    $r = docker inspect -f '{{.State.Running}}' jarvis-postgres 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $r.Trim() -ne 'true') { return $false }
    docker exec jarvis-postgres pg_isready -U jarvis -d jarvis_missions 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Test-Step 'Redis (container + PING)' {
    $r = docker inspect -f '{{.State.Running}}' jarvis-redis 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $r.Trim() -ne 'true') { return $false }
    $out = docker exec jarvis-redis redis-cli PING 2>&1 | Out-String
    return ($out -match 'PONG')
}

Test-Step 'Control Plane /health (8001)' {
    $r = Invoke-WebRequest -Uri 'http://localhost:8001/health' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-Step 'Command Center dev server (5173)' {
    $r = Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-Step 'OpenClaw Gateway port 18789 listening' {
    return (@(Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue).Count -gt 0)
}

Test-Step 'OpenClaw Gateway HTTP GET /' {
    $r = Invoke-WebRequest -Uri 'http://localhost:18789' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-Step 'LobsterBoard HTTP GET /' {
    $r = Invoke-WebRequest -Uri 'http://localhost:8080' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-Step 'Ollama HTTP GET /' {
    $r = Invoke-WebRequest -Uri 'http://localhost:11434' -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-Step 'DashClaw Vercel site' {
    $r = Invoke-WebRequest -Uri 'https://jarvis-dashclaw.vercel.app' -UseBasicParsing -TimeoutSec 25
    return ($r.StatusCode -eq 200)
}

$total = $pass + $fail
Write-Host ""
Write-Host "Summary: $pass/9 checks passed." -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Yellow' })
Write-Host "PHASE8 infrastructure $pass 9"
if ($fail -gt 0) { exit 1 }
exit 0
