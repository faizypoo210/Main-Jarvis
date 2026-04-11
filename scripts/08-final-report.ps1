#Requires -Version 5.1
# Phase 8: Run Phase 8 test scripts and write docs/08-deployment-report.txt.
# Core pass = infrastructure core + gateway + LAN + operator APIs + workspace governance (extended infra + external probes optional).
$ErrorActionPreference = 'Continue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$DocsDir = Join-Path $RepoRoot 'docs'
if (-not (Test-Path -LiteralPath $DocsDir)) {
    New-Item -ItemType Directory -Path $DocsDir -Force | Out-Null
}
$ReportPath = Join-Path $DocsDir '08-deployment-report.txt'

function Invoke-TestScript {
    param([string]$Path)
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Path 2>&1 | Out-String
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = -1 }
    return @{ Output = $out; ExitCode = $code }
}

function Get-Phase8Metric {
    param([string]$Text, [string]$Name)
    if ($Name -eq 'external_probes' -and $Text -match 'PHASE8 external_probes skipped') {
        return 'skipped (no tokens)'
    }
    $esc = [regex]::Escape($Name)
    if ($Text -match "PHASE8 $esc (\d+) (\d+)") {
        return "$($matches[1])/$($matches[2])"
    }
    return '?/?'
}

$sInfra = Join-Path $ScriptDir '08-test-infrastructure.ps1'
$sGw = Join-Path $ScriptDir '08-test-gateway.ps1'
$sMc = Join-Path $ScriptDir '08-test-mission-control.ps1'
$sLan = Join-Path $ScriptDir '08-test-lan-access.ps1'
$sFlow = Join-Path $ScriptDir '08-test-full-flow.ps1'
$sOperator = Join-Path $ScriptDir '08-smoke-operator-control-plane.ps1'
$sExternal = Join-Path $ScriptDir '08-smoke-external-probes.ps1'
$sWsGov = Join-Path $ScriptDir '08-smoke-workspace-governance.ps1'

$rInfra = Invoke-TestScript $sInfra
$rGw = Invoke-TestScript $sGw
$rMc = Invoke-TestScript $sMc
$rLan = Invoke-TestScript $sLan
$rFlow = Invoke-TestScript $sFlow
$rOperator = Invoke-TestScript $sOperator
$rExternal = Invoke-TestScript $sExternal
$rWsGov = Invoke-TestScript $sWsGov

$mInfraCore = Get-Phase8Metric $rInfra.Output 'infrastructure_core'
$mInfraExt = Get-Phase8Metric $rInfra.Output 'infrastructure_extended'
$mGw = Get-Phase8Metric $rGw.Output 'gateway'
$mMc = Get-Phase8Metric $rMc.Output 'missioncontrol'
$mLan = Get-Phase8Metric $rLan.Output 'lan'
$mFlow = Get-Phase8Metric $rFlow.Output 'fullflow'
$mOperator = Get-Phase8Metric $rOperator.Output 'operator_apis'
$mExternal = Get-Phase8Metric $rExternal.Output 'external_probes'
$mWsGov = Get-Phase8Metric $rWsGov.Output 'workspace_governance'

$corePass = ($rInfra.ExitCode -eq 0) -and ($rGw.ExitCode -eq 0) -and ($rLan.ExitCode -eq 0) -and ($rOperator.ExitCode -eq 0) -and ($rWsGov.ExitCode -eq 0)
$overallCore = if ($corePass) { 'PASS' } else { 'FAIL' }

$extOptionalOk = ($rMc.ExitCode -eq 0) -and ($rFlow.ExitCode -eq 0)
$externalClass = if ($rExternal.ExitCode -eq 0) { 'PASS_OR_SKIP' } else { 'FAIL' }

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('JARVIS Deployment Report (governed stack)')
[void]$sb.AppendLine('==========================================')
[void]$sb.AppendLine('CORE (required for green core line)')
[void]$sb.AppendLine("  Infrastructure core (Postgres, Redis, CP /health, gateway):  $mInfraCore passed")
[void]$sb.AppendLine("  Gateway + agent checks (openclaw):                          $mGw passed")
[void]$sb.AppendLine("  LAN access probes:                                          $mLan passed")
[void]$sb.AppendLine("  Control plane operator APIs (system health, activity, memory, heartbeat, evals, updates, approvals): $mOperator passed")
[void]$sb.AppendLine("  Workspace governance audit (manifest):                     $mWsGov passed")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('EXTENDED / INFORMATIONAL (do not block core on their own)')
[void]$sb.AppendLine("  Infrastructure extended (CC 5173, LobsterBoard, Ollama, DashClaw web): $mInfraExt (warn-only rows)")
[void]$sb.AppendLine("  Legacy openclaw-mission-control API (optional):               $mMc passed")
[void]$sb.AppendLine("  Full flow (OpenClaw agent turns):                           $mFlow passed")
[void]$sb.AppendLine("  External provider probes (GitHub/Gmail tokens):           $mExternal (skipped if no token; fail only if token set but API fails)")
[void]$sb.AppendLine('')
[void]$sb.AppendLine("Overall CORE stack: $overallCore")
[void]$sb.AppendLine("Optional suites (legacy UI, full-flow, external): external=$externalClass extended_ok=$extOptionalOk")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('Synthetic governed rehearsal (not run by this script): scripts/13-rehearse-golden-path.ps1')
[void]$sb.AppendLine('Live stack E2E (not run by this script): scripts/09-smoke-test-e2e.ps1, scripts/14-rehearse-live-stack.ps1')

Set-Content -Path $ReportPath -Value $sb.ToString() -Encoding UTF8

Write-Host $sb.ToString()

if (-not $corePass) {
    Write-Host "Core checks failed (infrastructure core, gateway, LAN, operator APIs, or workspace governance)." -ForegroundColor Red
    exit 1
}
if ($rExternal.ExitCode -ne 0) {
    Write-Host "Note: external provider probes failed (token present but API error). Core still passed." -ForegroundColor Yellow
}
Write-Host "Phase 8 core checks passed." -ForegroundColor Green
exit 0
