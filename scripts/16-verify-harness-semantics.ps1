#Requires -Version 5.1
<#
.SYNOPSIS
  Fast regression check for synthetic isolation markers and live-stack / benchmark harness parsing (no full stack required).

.DESCRIPTION
  - Asserts 13-rehearse-golden-path.ps1 still contains synthetic rehearsal context markers.
  - Runs fixture-based tests on Get-LiveStackHarnessParseResult and Get-HarnessReportSummary (same logic as 15).
  Does not start control plane, Redis, or coordinators.
#>
$ErrorActionPreference = 'Stop'

$Root = Split-Path $PSScriptRoot -Parent
$Golden13 = Join-Path $PSScriptRoot '13-rehearse-golden-path.ps1'
$Lib = Join-Path $PSScriptRoot 'lib\Parse-LiveStackHarnessOutput.ps1'

$failures = 0
function Assert-True([string]$Name, [bool]$Cond, [string]$Detail = '') {
    if ($Cond) {
        Write-Host "[OK] $Name" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $Name $Detail" -ForegroundColor Red
        $script:failures++
    }
}

Write-Host ""
Write-Host "=== 16-verify-harness-semantics ===" -ForegroundColor Cyan

# --- 1) Golden path script contains isolation markers ---
$g13 = Get-Content -LiteralPath $Golden13 -Raw -ErrorAction Stop
Assert-True '13 contains rehearsal_mode synthetic_api_only' ($g13 -match 'synthetic_api_only')
Assert-True '13 contains skip_runtime_publish' ($g13 -match 'skip_runtime_publish')
Assert-True '13 contains Redis XLEN isolation check' ($g13 -match 'Get-JarvisCommandsStreamLength|jarvis\.commands')

# --- 2) Parser library loads ---
if (-not (Test-Path -LiteralPath $Lib)) {
    Write-Host "[FAIL] Missing $Lib" -ForegroundColor Red
    exit 1
}
. $Lib

# --- 3) Fixture: ideal pass ---
$idealOut = @"
noise before
LIVE_STACK_PASS mission_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
tail
"@
$r1 = Get-LiveStackHarnessParseResult -CombinedOutput $idealOut -ExitCode 0
Assert-True 'ideal: outcome_class pass' ($r1.outcome_class -eq 'pass')
Assert-True 'ideal: hard_failure false' (-not $r1.hard_failure)
Assert-True 'ideal: mission_id parsed' ($r1.mission_id -eq 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')

$r1b = Get-LiveStackHarnessParseResult -CombinedOutput $idealOut -ExitCode 1
Assert-True 'ideal+nonzero exit: hard_failure' ($r1b.hard_failure -eq $true)

# --- 4) Fixture: known_nonblocking ---
$nbOut = @"
[PASS] something
LIVE_STACK_RESULT status=known_nonblocking classification=policy_allowed_execution mission_id=11111111-2222-3333-4444-555555555555 mission_status=active bundle_fetch_ok=true
LIVE_STACK_PASS mission_id=11111111-2222-3333-4444-555555555555 outcome=known_nonblocking
"@
$r2 = Get-LiveStackHarnessParseResult -CombinedOutput $nbOut -ExitCode 0
Assert-True 'nonblocking: outcome_class known_nonblocking' ($r2.outcome_class -eq 'known_nonblocking')
Assert-True 'nonblocking: classification policy_allowed_execution' ($r2.classification -eq 'policy_allowed_execution')
Assert-True 'nonblocking: hard_failure false' (-not $r2.hard_failure)
Assert-True 'nonblocking: mission_id' ($r2.mission_id -eq '11111111-2222-3333-4444-555555555555')

# --- 5) Fixture: hard fail with stage ---
$failOut = @"
LIVE_STACK_FAIL stage=REDIS
"@
$r3 = Get-LiveStackHarnessParseResult -CombinedOutput $failOut -ExitCode 1
Assert-True 'fail: hard_failure' ($r3.hard_failure -eq $true)
Assert-True 'fail: failure_stage REDIS' ($r3.failure_stage -eq 'REDIS')

# --- 6) FAIL wins if both present (strict precedence) ---
$mixed = @"
LIVE_STACK_RESULT status=known_nonblocking classification=policy_allowed_execution mission_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
LIVE_STACK_FAIL stage=CMD
"@
$r4 = Get-LiveStackHarnessParseResult -CombinedOutput $mixed -ExitCode 0
Assert-True 'precedence: FAIL over RESULT' ($r4.hard_failure -eq $true -and $r4.outcome_class -eq 'hard_fail')

# --- 7) Report summary ---
$mock = @(
    @{ type = 'synthetic'; hard_failure = $false; outcome_class = 'pass' },
    @{ type = 'live_stack'; hard_failure = $false; outcome_class = 'known_nonblocking' }
)
$s = Get-HarnessReportSummary -Rehearsals $mock
Assert-True 'summary: overall_pass true with known_nonblocking' ($s.overall_pass -eq $true)
Assert-True 'summary: overall_strict_pass false' ($s.overall_strict_pass -eq $false)
Assert-True 'summary: harness findings flag' ($s.summary_has_known_harness_findings -eq $true)
Assert-True 'summary: runtime label' ($s.runtime_health_label -eq 'healthy-with-known-harness-findings')

$mock2 = @(
    @{ type = 'synthetic'; hard_failure = $false; outcome_class = 'pass' },
    @{ type = 'live_stack'; hard_failure = $false; outcome_class = 'pass' }
)
$s2 = Get-HarnessReportSummary -Rehearsals $mock2
Assert-True 'summary: strict pass' ($s2.overall_strict_pass -eq $true -and $s2.runtime_health_label -eq 'healthy')

$mock3 = @(
    @{ type = 'synthetic'; hard_failure = $true; outcome_class = 'hard_fail' }
)
$s3 = Get-HarnessReportSummary -Rehearsals $mock3
Assert-True 'summary: failing' ($s3.runtime_health_label -eq 'failing' -and -not $s3.overall_pass)

Write-Host ""
if ($failures -eq 0) {
    Write-Host "HARNESS_SEMANTICS_PASS checks=all" -ForegroundColor Green
    exit 0
}
Write-Host "HARNESS_SEMANTICS_FAIL failures=$failures" -ForegroundColor Red
exit 1
