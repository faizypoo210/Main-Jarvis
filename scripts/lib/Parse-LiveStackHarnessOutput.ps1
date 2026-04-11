#Requires -Version 5.1
<#
.SYNOPSIS
  Parse combined stdout/stderr from scripts/14-rehearse-live-stack.ps1 for benchmark harness classification.

.NOTES
  Used by 15-benchmark-operator-loop.ps1 and 16-verify-harness-semantics.ps1.
  Precedence: LIVE_STACK_FAIL > LIVE_STACK_RESULT known_nonblocking > LIVE_STACK_PASS.
#>

function Get-LiveStackHarnessParseResult {
    param(
        [string]$CombinedOutput,
        [int]$ExitCode
    )
    $t = if ($null -eq $CombinedOutput) { '' } else { $CombinedOutput }

    # 1) Hard failure (any line announcing LIVE_STACK_FAIL)
    if ($t -match '(?m)LIVE_STACK_FAIL') {
        $stage = $null
        if ($t -match '(?m)LIVE_STACK_FAIL\s+stage=(\w+)') {
            $stage = $Matches[1]
        }
        return @{
            hard_failure     = $true
            outcome_class    = 'hard_fail'
            classification   = $null
            mission_id       = $null
            pass             = $false
            failure_stage    = $stage
            known_findings   = @()
            parse_confidence = 'high'
        }
    }

    # 2) Known non-blocking policy path (must match RESULT line from 14)
    if ($t -match 'LIVE_STACK_RESULT\s+status=known_nonblocking\s+classification=(\S+)\s+mission_id=([a-f0-9-]+)') {
        return @{
            hard_failure     = $false
            outcome_class    = 'known_nonblocking'
            classification   = $Matches[1]
            mission_id       = $Matches[2]
            pass             = $true
            failure_stage    = $null
            known_findings   = @('policy_allowed_execution_before_approval_gate')
            parse_confidence = 'high'
        }
    }

    # 3) Ideal pass (LIVE_STACK_PASS; exit code still gates hard_failure)
    if ($t -match 'LIVE_STACK_PASS\s+mission_id=([a-f0-9-]+)') {
        $mid = $Matches[1]
        $hard = ($ExitCode -ne 0)
        return @{
            hard_failure     = $hard
            outcome_class    = if ($hard) { 'hard_fail' } else { 'pass' }
            classification   = $null
            mission_id       = $mid
            pass             = -not $hard
            failure_stage    = $null
            known_findings   = @()
            parse_confidence = 'high'
        }
    }

    # 4) Unrecognized output
    $hard = ($ExitCode -ne 0)
    return @{
        hard_failure     = $hard
        outcome_class    = if ($hard) { 'hard_fail' } else { 'pass' }
        classification   = $null
        mission_id       = $null
        pass             = -not $hard
        failure_stage    = $null
        known_findings   = @()
        parse_confidence = 'low'
        parse_note       = if ($hard) { 'Non-zero exit without LIVE_STACK_FAIL line' } else { 'Zero exit without LIVE_STACK_PASS/RESULT line' }
    }
}

function Get-HarnessReportSummary {
    <#
    Mirrors schema 1.1 summary fields in 15-benchmark-operator-loop.ps1 from rehearsal objects with hard_failure / outcome_class.
    #>
    param([array]$Rehearsals)
    $anyHard = $false
    foreach ($r in $Rehearsals) {
        if ($r.hard_failure) { $anyHard = $true; break }
    }
    $overall_pass = -not $anyHard
    $strictOk = $true
    foreach ($r in $Rehearsals) {
        if ($r.outcome_class -ne 'pass') { $strictOk = $false; break }
    }
    $hasHarness = $false
    foreach ($r in $Rehearsals) {
        if ($r.outcome_class -eq 'known_nonblocking') { $hasHarness = $true; break }
    }
    $health = if (-not $overall_pass) {
        'failing'
    } elseif ($hasHarness) {
        'healthy-with-known-harness-findings'
    } else {
        'healthy'
    }
    return @{
        overall_pass                        = $overall_pass
        overall_strict_pass               = $strictOk
        summary_has_known_harness_findings = $hasHarness
        runtime_health_label              = $health
    }
}
