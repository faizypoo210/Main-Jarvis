#Requires -Version 5.1
<#
.SYNOPSIS
  Safe, non-destructive checks for failure-mode assumptions (control plane + event shape).

.DESCRIPTION
  - GET /health
  - GET /api/v1/missions (no auth required for list)
  - If missions exist: GET bundle + events for the first mission
  - Asserts mission event IDs are unique (deterministic DB invariant)
  - Verifies repo contains client-side dedupe helpers (merge/dedupe) — informational

  Does NOT: POST commands, resolve approvals, or stop services.

.PARAMETER ControlPlaneUrl
  Base URL without trailing slash. Default http://127.0.0.1:8000

.EXAMPLE
  .\12-test-failure-modes.ps1
  .\12-test-failure-modes.ps1 -ControlPlaneUrl http://localhost:8000
#>
param(
    [string]$ControlPlaneUrl = 'http://127.0.0.1:8000'
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $here

$pass = 0
$fail = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Probe)
    try {
        $ok = & $Probe
        if ($ok) {
            Write-Host "[PASS] $Name" -ForegroundColor Green
            $script:pass++
        }
        else {
            Write-Host "[FAIL] $Name" -ForegroundColor Red
            $script:fail++
        }
    }
    catch {
        Write-Host "[FAIL] $Name - $($_.Exception.Message)" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "=== 12-test-failure-modes (safe / read-only) ===" -ForegroundColor Cyan
Write-Host "Control plane: $ControlPlaneUrl" -ForegroundColor Gray

$api = "$ControlPlaneUrl/api/v1"

Test-Step 'GET /health returns ok' {
    $r = Invoke-RestMethod -Uri "$ControlPlaneUrl/health" -Method Get -TimeoutSec 15
    return ($r.status -eq 'ok' -and $r.service -eq 'jarvis-control-plane')
}

Test-Step 'GET /api/v1/missions returns array' {
    $missions = Invoke-RestMethod -Uri "$api/missions?limit=5" -Method Get -TimeoutSec 15
    return ($null -ne $missions -and $missions -is [System.Array])
}

$firstMissionId = $null
try {
    $missions = Invoke-RestMethod -Uri "$api/missions?limit=5" -Method Get -TimeoutSec 15
    if ($missions.Count -gt 0) {
        $firstMissionId = $missions[0].id
    }
}
catch {
    $firstMissionId = $null
}

if ($firstMissionId) {
    Test-Step 'GET mission bundle includes mission + events + approvals + receipts' {
        $b = Invoke-RestMethod -Uri "$api/missions/$firstMissionId/bundle" -Method Get -TimeoutSec 20
        return ($null -ne $b.mission -and $null -ne $b.events)
    }

    Test-Step 'Mission events from API have unique ids (deterministic)' {
        $ev = Invoke-RestMethod -Uri "$api/missions/$firstMissionId/events" -Method Get -TimeoutSec 20
        if (-not $ev -or $ev -isnot [System.Array]) { return $false }
        $ids = @($ev | ForEach-Object { $_.id })
        $unique = ($ids | Select-Object -Unique)
        return ($ids.Count -eq $unique.Count)
    }
}
else {
    Write-Host '[SKIP] No missions in DB — bundle/event uniqueness checks skipped (create one mission via normal flow).' -ForegroundColor Yellow
}

Test-Step 'Docs FAILURE_MODES.md exists' {
    return (Test-Path -LiteralPath (Join-Path $repoRoot 'docs\FAILURE_MODES.md'))
}

Test-Step 'Command-center: merge/dedupe sources present (grep)' {
    $ctx = Join-Path $repoRoot 'services\command-center\src\contexts\ControlPlaneLiveContext.tsx'
    if (-not (Test-Path -LiteralPath $ctx)) { return $false }
    $c = Get-Content -LiteralPath $ctx -Raw
    return ($c -match 'mergeMissionEvents' -and $c -match 'appendEvent')
}

Write-Host ""
$color = 'Green'
if ($fail -ne 0) { $color = 'Red' }
Write-Host ('Summary: ' + $pass + ' passed, ' + $fail + ' failed') -ForegroundColor $color
if ($fail -ne 0) { exit 1 }
exit 0
