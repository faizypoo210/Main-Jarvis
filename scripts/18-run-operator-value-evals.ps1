#Requires -Version 5.1
<#
.SYNOPSIS
  Fetch Operator Value Evals v1 from the control plane and write JSON + a short human summary under docs/reports/.

.DESCRIPTION
  Read-only GET /api/v1/operator/evals — bounded aggregates from mission truth (no subjective scoring).

.PARAMETER ControlPlaneUrl
  Base URL (no trailing slash). Defaults to $env:CONTROL_PLANE_URL or http://127.0.0.1:8001.

.PARAMETER ApiKey
  Defaults to $env:CONTROL_PLANE_API_KEY.

.PARAMETER WindowHours
  Rolling UTC window (default 168 = 7 days, max 720).

.PARAMETER GroupByDay
  If set, adds group_by=day for per-UTC-day timeseries.

.EXAMPLE
  $env:CONTROL_PLANE_API_KEY = '...'
  .\scripts\18-run-operator-value-evals.ps1
#>
param(
    [string]$ControlPlaneUrl = "",
    [string]$ApiKey = "",
    [int]$WindowHours = 168,
    [switch]$GroupByDay
)

$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path $ScriptDir -Parent
$ReportsDir = Join-Path $RepoRoot 'docs\reports'
if (-not (Test-Path $ReportsDir)) {
    New-Item -ItemType Directory -Path $ReportsDir | Out-Null
}

$Base = if ($ControlPlaneUrl -and $ControlPlaneUrl.Trim()) { $ControlPlaneUrl.TrimEnd('/') } else {
    if ($env:CONTROL_PLANE_URL -and $env:CONTROL_PLANE_URL.Trim()) { $env:CONTROL_PLANE_URL.TrimEnd('/') } else { 'http://127.0.0.1:8001' }
}
$Key = if ($ApiKey) { $ApiKey } else { $env:CONTROL_PLANE_API_KEY }
if (-not $Key -or -not $Key.Trim()) {
    throw 'Set CONTROL_PLANE_API_KEY or pass -ApiKey.'
}

$qs = "window_hours=$WindowHours"
if ($GroupByDay) { $qs += "&group_by=day" }
$uri = "$Base/api/v1/operator/evals?$qs"

$headers = @{
    'x-api-key'       = $Key
    'Accept'          = 'application/json'
}

try {
    $resp = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get
} catch {
    throw "GET operator/evals failed: $_"
}

$ts = [DateTimeOffset]::UtcNow.ToString("yyyyMMdd-HHmmss")
$jsonPath = Join-Path $ReportsDir "operator-value-evals-$ts.json"
$txtPath = Join-Path $ReportsDir "operator-value-evals-$ts.txt"

$resp | ConvertTo-Json -Depth 25 | Set-Content -Path $jsonPath -Encoding UTF8

$mm = $resp.mission_metrics
$am = $resp.approval_metrics
$im = $resp.integration_metrics
$hb = $resp.heartbeat_metrics
$lines = @(
    "Operator Value Evals v1 — $ts UTC",
    "Window: $($resp.summary.window_start_utc) -> $($resp.summary.window_end_utc) ($($resp.window_hours)h)",
    "",
    "Missions created: $($mm.missions_created_in_window) | complete (terminal in window): $($mm.missions_reached_complete_in_window) | failed (terminal): $($mm.missions_reached_failed_in_window)",
    "Approvals: requested=$($am.approvals_requested_in_window) resolved=$($am.approvals_resolved_in_window) denied_events=$($am.approvals_denied_in_window) pending_now=$($am.pending_now)",
    "Integrations (receipts): gh +$($im.github_issue_created) / -$($im.github_issue_failed) | gmail draft +$($im.gmail_draft_created) / -$($im.gmail_draft_failed) | send +$($im.gmail_draft_sent) / -$($im.gmail_draft_send_failed)",
    "Heartbeat: opened=$($hb.findings_first_seen_in_window) resolved=$($hb.findings_resolved_in_window) open_now=$($hb.open_findings_total)",
    "",
    "JSON: $jsonPath"
)
$lines | Set-Content -Path $txtPath -Encoding UTF8

Write-Host ($lines -join "`n")

exit 0
