#Requires -Version 5.1
# Phase 8: LAN IP HTTP probes (read-only); exits 0 only if all 5 pass.
$ErrorActionPreference = 'Continue'

$Lan = '10.0.0.249'
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
            Write-Host "[FAIL] $Name"
            $script:fail++
        }
    } catch {
        Write-Host "[FAIL] $Name - $($_.Exception.Message)"
        $script:fail++
    }
}

Write-Host "=== 08-test-lan-access (read-only) ===" -ForegroundColor Cyan

Test-Step "GET http://${Lan}:3000" {
    $r = Invoke-WebRequest -Uri "http://${Lan}:3000" -UseBasicParsing -TimeoutSec 20
    return ($r.StatusCode -eq 200)
}

Test-Step "GET http://${Lan}:3001/health" {
    $r = Invoke-WebRequest -Uri "http://${Lan}:3001/health" -UseBasicParsing -TimeoutSec 20
    return ($r.StatusCode -eq 200)
}

Test-Step "GET http://${Lan}:18789" {
    $r = Invoke-WebRequest -Uri "http://${Lan}:18789" -UseBasicParsing -TimeoutSec 20
    return ($r.StatusCode -eq 200)
}

Test-Step "GET http://${Lan}:8080" {
    $r = Invoke-WebRequest -Uri "http://${Lan}:8080" -UseBasicParsing -TimeoutSec 20
    return ($r.StatusCode -eq 200)
}

Test-Step "GET http://${Lan}:11434" {
    $r = Invoke-WebRequest -Uri "http://${Lan}:11434" -UseBasicParsing -TimeoutSec 20
    return ($r.StatusCode -eq 200)
}

Write-Host ""
Write-Host "Summary: $pass/5 checks passed." -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Yellow' })
Write-Host "Open these URLs from your phone browser while on the same WiFi to verify access." -ForegroundColor Yellow
Write-Host "PHASE8 lan $pass 5"
if ($fail -gt 0) { exit 1 }
exit 0
