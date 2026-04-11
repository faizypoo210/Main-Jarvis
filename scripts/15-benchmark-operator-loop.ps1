#Requires -Version 5.1
<#
.SYNOPSIS
  Operator benchmark loop — measures API-truth timings from a synthetic rehearsal plus optional live-stack run.

.DESCRIPTION
  Safe, non-destructive: creates normal missions/approvals/receipts like 13-rehearse-golden-path.ps1.
  Records:
    - HTTP round-trips (health, command, approvals, decision, receipt, bundle)
    - Event-derived deltas from GET /api/v1/missions/{id}/events (same source as mission timing UI)
    - Optional SSE first-byte timings (curl) for two sequential connections (client reconnect proxy)
    - Optional: invoke 14-rehearse-live-stack.ps1 and attach wall-clock + event-derived timings if pass

  Outputs: console summary + JSON under docs/reports/

.PARAMETER ControlPlaneUrl
.PARAMETER IncludeLiveStack
  Run scripts/14-rehearse-live-stack.ps1 after synthetic (requires Redis/coordinator/executor).
.PARAMETER SkipSseProbe
  Do not measure SSE TTFB (no curl dependency / avoid stream noise).
.PARAMETER OutputDir
  Default: repo docs/reports relative to script parent.
.PARAMETER LiveStackPollTimeoutSec
  Passed to 14-rehearse-live-stack.ps1
.PARAMETER EnvironmentNotes
  Free text stored in the JSON report (e.g. branch name, machine, “before token rotation”).
#>
param(
    [string]$ControlPlaneUrl = "",
    [switch]$IncludeLiveStack,
    [switch]$SkipSseProbe,
    [string]$OutputDir = "",
    [int]$LiveStackPollTimeoutSec = 300,
    [string]$EnvironmentNotes = ""
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path $PSScriptRoot -Parent
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $RepoRoot "docs\reports"
}
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

function Get-ApiKey {
    $k = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_API_KEY', 'User')
    if ([string]::IsNullOrWhiteSpace($k)) { $k = $env:CONTROL_PLANE_API_KEY }
    if ([string]::IsNullOrWhiteSpace($k)) { $k = $env:JARVIS_SMOKE_API_KEY }
    return $k
}

function Get-CpBase {
    param([string]$Url)
    if (-not [string]::IsNullOrWhiteSpace($Url)) { return $Url.TrimEnd('/') }
    $u = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_URL', 'User')
    if ([string]::IsNullOrWhiteSpace($u)) { $u = $env:CONTROL_PLANE_URL }
    if ([string]::IsNullOrWhiteSpace($u)) { $u = 'http://127.0.0.1:8001' }
    return $u.TrimEnd('/')
}

function Measure-StopwatchMs {
    param([scriptblock]$Action)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $result = & $Action
    $sw.Stop()
    return @{ ms = [long]$sw.ElapsedMilliseconds; result = $result }
}

function Parse-IsoToOffset {
    param([object]$Value)
    if ($null -eq $Value) { return $null }
    $s = $Value.ToString().Trim()
    if ([string]::IsNullOrWhiteSpace($s)) { return $null }
    try {
        return [DateTimeOffset]::Parse($s, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind)
    } catch {
        return $null
    }
}

function Get-DeltaMs {
    param($Start, $End)
    if ($null -eq $Start -or $null -eq $End) { return $null }
    return [long]($End - $Start).TotalMilliseconds
}

function Get-FirstEventTime {
    param($Events, [string]$EventType)
    $list = @($Events | Where-Object { $_.event_type -eq $EventType } | Sort-Object created_at, id)
    if ($list.Count -eq 0) { return $null }
    return Parse-IsoToOffset $list[0].created_at
}

function Invoke-SseTtfbCurl {
    param([string]$StreamUrl, [string]$ApiKey, [int]$MaxSec = 15)
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) {
        return @{ ok = $false; ms = $null; note = 'curl.exe not on PATH; install or use SkipSseProbe' }
    }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & curl.exe -s -o NUL -w "%{time_starttransfer}" -H "x-api-key: $ApiKey" --max-time $MaxSec $StreamUrl 2>&1
        $line = if ($out -is [array]) { $out[-1] } else { $out }
        $ms = $null
        if ($line -match '^[\d\.]+$') {
            $sec = [double]$line
            $ms = [long][math]::Round($sec * 1000.0)
        }
        if ($null -eq $ms) {
            return @{ ok = $false; ms = $null; note = "curl TTFB parse failed: $line" }
        }
        return @{ ok = $true; ms = $ms; note = 'time_starttransfer (seconds->ms); first response byte' }
    } catch {
        return @{ ok = $false; ms = $null; note = $_.Exception.Message }
    } finally {
        $ErrorActionPreference = $prev
    }
}

function New-ReportRoot {
    return @{
        schema_version = '1.0'
        timestamp_utc    = (Get-Date).ToUniversalTime().ToString('o')
        environment_notes = @{}
        rehearsals       = @()
        sse              = @{}
        notes            = @()
    }
}

$Base = Get-CpBase -Url $ControlPlaneUrl
$Api = "$Base/api/v1"
$ApiKey = Get-ApiKey

$report = New-ReportRoot
$notesExtra = $EnvironmentNotes
if ([string]::IsNullOrWhiteSpace($notesExtra)) { $notesExtra = $env:JARVIS_BENCH_NOTES }
$report.environment_notes = @{
    control_plane_url    = $Base
    hostname             = $env:COMPUTERNAME
    ps_version           = $PSVersionTable.PSVersion.ToString()
    include_live_stack   = [bool]$IncludeLiveStack
    skip_sse_probe       = [bool]$SkipSseProbe
    operator_notes       = if ([string]::IsNullOrWhiteSpace($notesExtra)) { $null } else { $notesExtra.Trim() }
}

Write-Host ""
Write-Host "Jarvis operator benchmark (API-truth timings)" -ForegroundColor White
Write-Host "Control plane: $Base" -ForegroundColor DarkGray
Write-Host "Report dir: $OutputDir" -ForegroundColor DarkGray

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Host "[FAIL] CONTROL_PLANE_API_KEY not set." -ForegroundColor Red
    exit 1
}

$Headers = @{
    'x-api-key'    = $ApiKey
    'Content-Type' = 'application/json; charset=utf-8'
}

# --- SSE probe (two sequential connects = client reconnect proxy; not server failure injection) ---
if (-not $SkipSseProbe) {
    $streamUrl = "$Base/api/v1/updates/stream"
    Write-Host ""
    Write-Host "=== SSE TTFB (two connects) ===" -ForegroundColor Cyan
    $a = Invoke-SseTtfbCurl -StreamUrl $streamUrl -ApiKey $ApiKey
    Start-Sleep -Milliseconds 400
    $b = Invoke-SseTtfbCurl -StreamUrl $streamUrl -ApiKey $ApiKey
    $report.sse = @{
        stream_url                   = $streamUrl
        first_connect_ttfb_ms        = $a.ms
        second_connect_ttfb_ms       = $b.ms
        first_connect_ok             = $a.ok
        second_connect_ok            = $b.ok
        interpretation               = 'HTTP client time to first byte; proxy for reconnect readiness, not browser UI or server-side disconnect.'
        notes                        = @($a.note, $b.note)
    }
    Write-Host "  First connect TTFB: $($a.ms) ms ($($a.note))" -ForegroundColor $(if ($a.ok) { 'Green' } else { 'Yellow' })
    Write-Host "  Second connect TTFB: $($b.ms) ms ($($b.note))" -ForegroundColor $(if ($b.ok) { 'Green' } else { 'Yellow' })
}

# --- Synthetic timed golden path ---
$synthetic = @{
    type       = 'synthetic'
    pass       = $false
    mission_id = $null
    stages     = @{}
    timings_ms = @{}
    anomalies  = @()
    http_roundtrip_ms = @{}
    event_deltas_ms   = @{}
}

try {
    $swHealth = Measure-StopwatchMs { Invoke-RestMethod -Uri "$Base/health" -Method Get -TimeoutSec 15 }
    $synthetic.stages['health'] = if ($swHealth.result.status -eq 'ok') { 'pass' } else { 'fail' }
    $synthetic.http_roundtrip_ms['health'] = $swHealth.ms
    if ($synthetic.stages['health'] -ne 'pass') {
        throw "GET /health status not ok"
    }

    $cmdText = 'Benchmark operator loop: synthetic path; status only.'
    $cmdBody = @{ text = $cmdText; source = 'command_center' } | ConvertTo-Json -Compress
    $swCmd = Measure-StopwatchMs { Invoke-RestMethod -Uri "$Api/commands" -Method Post -Headers $Headers -Body $cmdBody -TimeoutSec 60 }
    $MissionId = $swCmd.result.mission_id.ToString()
    $synthetic.mission_id = $MissionId
    $synthetic.http_roundtrip_ms['command_submission'] = $swCmd.ms

    $apBody = @{
        mission_id    = $MissionId
        action_type   = 'Benchmark execution step'
        risk_class    = 'amber'
        reason        = 'Operator benchmark — synthetic approval path.'
        requested_by  = 'benchmark_operator_loop'
        requested_via = 'command_center'
    } | ConvertTo-Json -Compress

    $swAp = Measure-StopwatchMs { Invoke-RestMethod -Uri "$Api/approvals" -Method Post -Headers $Headers -Body $apBody -TimeoutSec 60 }
    $ApprovalId = $swAp.result.id.ToString()
    $synthetic.http_roundtrip_ms['post_approval_request'] = $swAp.ms

    $events1 = Invoke-RestMethod -Uri "$Api/missions/$MissionId/events" -Method Get -TimeoutSec 30
    $tCreated = Get-FirstEventTime -Events $events1 -EventType 'created'
    $tApReq = Get-FirstEventTime -Events $events1 -EventType 'approval_requested'
    $synthetic.event_deltas_ms['created_to_approval_requested'] = Get-DeltaMs -Start $tCreated -End $tApReq

    $decBody = @{
        decision    = 'approved'
        decided_by  = 'operator'
        decided_via = 'command_center'
    } | ConvertTo-Json -Compress
    $swDec = Measure-StopwatchMs { Invoke-RestMethod -Uri "$Api/approvals/$ApprovalId/decision" -Method Post -Headers $Headers -Body $decBody -TimeoutSec 60 }
    $synthetic.http_roundtrip_ms['approval_decision_post'] = $swDec.ms

    $events2 = Invoke-RestMethod -Uri "$Api/missions/$MissionId/events" -Method Get -TimeoutSec 30
    $tApReq2 = Get-FirstEventTime -Events $events2 -EventType 'approval_requested'
    $tApRes = Get-FirstEventTime -Events $events2 -EventType 'approval_resolved'
    $synthetic.event_deltas_ms['approval_requested_to_resolved'] = Get-DeltaMs -Start $tApReq2 -End $tApRes

    $rcBody = @{
        mission_id   = $MissionId
        receipt_type = 'execution'
        source       = 'benchmark_operator_loop'
        summary      = 'Synthetic benchmark receipt.'
        payload      = @{ execution_meta = @{ lane = 'benchmark'; model = 'n/a' } }
    } | ConvertTo-Json -Compress -Depth 6
    $swRc = Measure-StopwatchMs { Invoke-RestMethod -Uri "$Api/receipts" -Method Post -Headers $Headers -Body $rcBody -TimeoutSec 60 }
    $synthetic.http_roundtrip_ms['post_receipt'] = $swRc.ms

    $events3 = Invoke-RestMethod -Uri "$Api/missions/$MissionId/events" -Method Get -TimeoutSec 30
    $tRc = Get-FirstEventTime -Events $events3 -EventType 'receipt_recorded'
    $synthetic.event_deltas_ms['approval_resolved_to_first_receipt'] = Get-DeltaMs -Start $tApRes -End $tRc
    $synthetic.event_deltas_ms['created_to_first_receipt'] = Get-DeltaMs -Start $tCreated -End $tRc

    $swBundle = Measure-StopwatchMs { Invoke-RestMethod -Uri "$Api/missions/$MissionId/bundle" -Method Get -TimeoutSec 30 }
    $bundle = $swBundle.result
    $synthetic.http_roundtrip_ms['bundle_get'] = $swBundle.ms

    $types = @(@($bundle.events) | ForEach-Object { $_.event_type })
    $bundleOk = ($types -contains 'created') -and ($types -contains 'approval_requested') -and ($types -contains 'approval_resolved') -and ($types -contains 'receipt_recorded')
    $synthetic.timings_ms['receipt_post_to_bundle_verify'] = [long]($swRc.ms + $swBundle.ms)
    $synthetic.timings_ms['interpretation_bundle_latency'] = 'Sum of receipt POST round-trip and bundle GET round-trip (wall); not a single server-side metric.'

    if ($bundleOk -and @($bundle.receipts).Count -ge 1) {
        $synthetic.stages['bundle_truth'] = 'pass'
        $synthetic.timings_ms['time_to_bundle_truth_consistency_ms'] = $synthetic.timings_ms['receipt_post_to_bundle_verify']
    } else {
        $synthetic.stages['bundle_truth'] = 'fail'
        $synthetic.anomalies += 'Bundle missing expected event types or receipts.'
    }

    $synthetic.stages['command'] = 'pass'
    $synthetic.stages['approval_create'] = 'pass'
    $synthetic.stages['approval_decide'] = 'pass'
    $synthetic.stages['receipt'] = 'pass'

    $synthetic.pass = ($synthetic.stages['bundle_truth'] -eq 'pass')
}
catch {
    $synthetic.pass = $false
    $synthetic.anomalies += $_.Exception.Message
    $report.notes += "Synthetic path exception: $($_.Exception.Message)"
}

$report.rehearsals += $synthetic

Write-Host ""
Write-Host "=== Synthetic rehearsal ===" -ForegroundColor Cyan
Write-Host "  mission_id=$($synthetic.mission_id) pass=$($synthetic.pass)" -ForegroundColor $(if ($synthetic.pass) { 'Green' } else { 'Red' })
Write-Host "  HTTP round-trips (ms): $($synthetic.http_roundtrip_ms | ConvertTo-Json -Compress)" -ForegroundColor DarkGray
Write-Host "  Event deltas (API truth, ms): $($synthetic.event_deltas_ms | ConvertTo-Json -Compress)" -ForegroundColor DarkGray

# --- Optional live stack ---
if ($IncludeLiveStack) {
    $live = @{
        type       = 'live_stack'
        pass       = $false
        mission_id = $null
        wall_clock_total_ms = $null
        stages     = @{}
        event_deltas_ms = @{}
        anomalies  = @()
        note       = 'Wall time includes coordinator/executor/DashClaw/OpenClaw; see LIVE_STACK_FAIL for stage on failure.'
    }
    $script14 = Join-Path $PSScriptRoot "14-rehearse-live-stack.ps1"
    if (-not (Test-Path $script14)) {
        $live.anomalies += "Missing $script14"
        $report.rehearsals += $live
        $report.notes += 'IncludeLiveStack set but 14-rehearse-live-stack.ps1 not found.'
    } else {
        Write-Host ""
        Write-Host "=== Live-stack rehearsal (14) ===" -ForegroundColor Cyan
        $shellExe = (Get-Command powershell.exe -ErrorAction SilentlyContinue).Source
        if (-not $shellExe) { $shellExe = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source }
        if (-not $shellExe) {
            $live.anomalies += 'powershell.exe / pwsh.exe not found; cannot spawn live-stack child.'
            $report.rehearsals += $live
            $report.notes += 'IncludeLiveStack failed: no shell executable.'
        } else {
        $swAll = [System.Diagnostics.Stopwatch]::StartNew()
        $outF = Join-Path $env:TEMP "jarvis-bench-ls-out-$PID.txt"
        $errF = Join-Path $env:TEMP "jarvis-bench-ls-err-$PID.txt"
        Remove-Item $outF, $errF -ErrorAction SilentlyContinue
        $argList = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script14,
            '-ControlPlaneUrl', $Base, '-PollTimeoutSec', "$LiveStackPollTimeoutSec"
        )
        try {
            $proc = Start-Process -FilePath $shellExe -ArgumentList $argList -WorkingDirectory $RepoRoot `
                -RedirectStandardOutput $outF -RedirectStandardError $errF -Wait -PassThru -NoNewWindow
            $lsCode = $proc.ExitCode
        } catch {
            $live.anomalies += $_.Exception.Message
            $lsCode = -1
        }
        $swAll.Stop()
        $live.wall_clock_total_ms = [long]$swAll.ElapsedMilliseconds
        $stdout = if (Test-Path $outF) { Get-Content -Path $outF -Raw -ErrorAction SilentlyContinue } else { '' }
        $stderr = if (Test-Path $errF) { Get-Content -Path $errF -Raw -ErrorAction SilentlyContinue } else { '' }
        if ($stdout) { Write-Host $stdout }
        if ($stderr -and $stderr.Trim().Length -gt 0) { Write-Host $stderr -ForegroundColor DarkYellow }
        $text = ($stdout + "`n" + $stderr)
        if ($text -match 'LIVE_STACK_PASS mission_id=([a-f0-9-]+)') {
            $live.mission_id = $Matches[1]
            $live.pass = ($lsCode -eq 0)
        }
        if ($text -match 'LIVE_STACK_FAIL stage=(\w+)') {
            $live.stages['failure'] = $Matches[1]
            $live.pass = $false
        }
        if ($lsCode -ne 0) { $live.pass = $false }

        if ($live.pass -and $live.mission_id) {
            try {
                $ev = Invoke-RestMethod -Uri "$Api/missions/$($live.mission_id)/events" -Method Get -TimeoutSec 30
                $tc = Get-FirstEventTime -Events $ev -EventType 'created'
                $tar = Get-FirstEventTime -Events $ev -EventType 'approval_requested'
                $tas = Get-FirstEventTime -Events $ev -EventType 'approval_resolved'
                $tr = Get-FirstEventTime -Events $ev -EventType 'receipt_recorded'
                $live.event_deltas_ms['created_to_approval_requested'] = Get-DeltaMs -Start $tc -End $tar
                $live.event_deltas_ms['approval_requested_to_resolved'] = Get-DeltaMs -Start $tar -End $tas
                $live.event_deltas_ms['approval_resolved_to_first_receipt'] = Get-DeltaMs -Start $tas -End $tr
                $live.event_deltas_ms['created_to_first_receipt'] = Get-DeltaMs -Start $tc -End $tr
            } catch {
                $live.anomalies += "Post-pass event fetch failed: $($_.Exception.Message)"
            }
        }

        Write-Host "  LIVE_STACK wall_ms=$($live.wall_clock_total_ms) pass=$($live.pass) mission_id=$($live.mission_id)" -ForegroundColor $(if ($live.pass) { 'Green' } else { 'Red' })
        $report.rehearsals += $live
        }
    }
}

# --- Write JSON ---
$allPass = $true
foreach ($r in $report.rehearsals) {
    if (-not $r.pass) { $allPass = $false; break }
}
$report['overall_pass'] = $allPass

$fileStamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
$outFile = Join-Path $OutputDir "operator-benchmark-$fileStamp.json"
$report | ConvertTo-Json -Depth 12 | Set-Content -Path $outFile -Encoding UTF8

Write-Host ""
Write-Host "Report written: $outFile" -ForegroundColor Green
Write-Host "overall_pass=$allPass" -ForegroundColor $(if ($allPass) { 'Green' } else { 'Red' })

$exitCode = 0
foreach ($r in $report.rehearsals) {
    if (-not $r.pass) { $exitCode = 1 }
}
exit $exitCode
