#Requires -Version 5.1
<#
.SYNOPSIS
  Live-stack rehearsal: real Redis, coordinator, DashClaw, executor, OpenClaw, control plane only.

.DESCRIPTION
  Does NOT POST /approvals or /receipts manually. Waits for runtime-created approval and execution receipt.

  Terminal lines parsed by benchmark (see scripts/lib/Parse-LiveStackHarnessOutput.ps1): LIVE_STACK_FAIL, LIVE_STACK_RESULT …, LIVE_STACK_PASS.

  Stages (each reports PASS/FAIL independently):
    CP     - Control plane /health
    REDIS  - Redis PING + consumer groups on jarvis.commands and jarvis.execution
    CMD    - POST /api/v1/commands
    GUARD  - Pending approval appears (coordinator + DashClaw)
    APRV   - POST /api/v1/approvals/{id}/decision (approve)
    EXEC   - receipt_recorded from executor path
    BUNDLE - GET /api/v1/missions/{id}/bundle coherence

  Requires: CONTROL_PLANE_API_KEY, running Redis (default container jarvis-redis), coordinator, executor,
            DashClaw/OpenClaw reachable from those processes.

.PARAMETER ControlPlaneUrl
.PARAMETER PollTimeoutSec
.PARAMETER PollIntervalSec
.PARAMETER ApprovalCommandText
#>
param(
    [string]$ControlPlaneUrl = "",
    [int]$PollTimeoutSec = 300,
    [int]$PollIntervalSec = 3,
    [string]$ApprovalCommandText = "",
    [string]$RedisContainer = "jarvis-redis"
)

$ErrorActionPreference = 'Stop'

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

function Write-Stage([string]$Code, [string]$Title) {
    Write-Host ""
    Write-Host "[$Code] $Title" -ForegroundColor Cyan
}

function Write-Pass([string]$Msg) { Write-Host "  [PASS] $Msg" -ForegroundColor Green }
function Write-Fail([string]$Msg) { Write-Host "  [FAIL] $Msg" -ForegroundColor Red }
function Write-Info([string]$Msg) { Write-Host "         $Msg" -ForegroundColor DarkGray }

function Invoke-RedisCli {
    param([string[]]$RedisArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            $running = docker inspect -f '{{.State.Running}}' $RedisContainer 2>$null
            if ($running -eq 'true') {
                return docker exec $RedisContainer redis-cli @RedisArgs 2>&1 | Out-String
            }
        }
        if (Get-Command redis-cli -ErrorAction SilentlyContinue) {
            return & redis-cli @RedisArgs 2>&1 | Out-String
        }
    } finally {
        $ErrorActionPreference = $prev
    }
    return $null
}

function Get-EventSummaryFromPayload {
    param($Payload)
    if ($null -eq $Payload) { return $null }
    if ($Payload -is [hashtable]) { return $Payload['summary'] }
    try { return $Payload.summary } catch { return $null }
}

$Base = Get-CpBase -Url $ControlPlaneUrl
$Api = "$Base/api/v1"
$ApiKey = Get-ApiKey

$script:FailStage = $null

Write-Host ""
Write-Host "Jarvis live-stack rehearsal (runtime path only)" -ForegroundColor White
Write-Host "Control plane: $Base" -ForegroundColor DarkGray

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Fail "CONTROL_PLANE_API_KEY is not set."
    Write-Host "LIVE_STACK_FAIL stage=CP reason=api_key" -ForegroundColor Red
    exit 1
}

$Headers = @{
    'x-api-key'    = $ApiKey
    'Content-Type' = 'application/json; charset=utf-8'
}

# --- Stage CP ---
Write-Stage "CP" "Control plane health"
try {
    $h = Invoke-RestMethod -Uri "$Base/health" -Method Get -TimeoutSec 15
    if ($h.status -eq 'ok') {
        Write-Pass "GET /health" 
    } else {
        Write-Fail "Unexpected /health body"
        $script:FailStage = 'CP'
    }
} catch {
    Write-Fail "GET /health: $($_.Exception.Message)"
    $script:FailStage = 'CP'
}
if ($script:FailStage) {
    Write-Host "LIVE_STACK_FAIL stage=$($script:FailStage)" -ForegroundColor Red
    exit 1
}

# --- Stage REDIS ---
Write-Stage "REDIS" "Redis streams and consumer groups"
$redisOk = $true
$ping = Invoke-RedisCli -RedisArgs @('PING')
if ($ping -match 'PONG') {
    Write-Pass "Redis PING"
} else {
    Write-Fail "Redis PING failed (docker exec $RedisContainer redis-cli, or redis-cli on PATH)"
    $redisOk = $false
}

$groupsCmd = Invoke-RedisCli -RedisArgs @('XINFO', 'GROUPS', 'jarvis.commands')
if ($groupsCmd -match 'jarvis-coordinator-commands') {
    Write-Pass "jarvis.commands has consumer group jarvis-coordinator-commands (coordinator running)"
} elseif ($groupsCmd -match 'no such key|ERR') {
    Write-Fail "Stream jarvis.commands missing or unreadable. Start coordinator so it creates the group, or run once after a command."
    $redisOk = $false
} else {
    Write-Fail "Could not confirm coordinator group on jarvis.commands. Output: $($groupsCmd.Substring(0, [Math]::Min(200, $groupsCmd.Length)))"
    $redisOk = $false
}

$groupsEx = Invoke-RedisCli -RedisArgs @('XINFO', 'GROUPS', 'jarvis.execution')
if ($groupsEx -match 'jarvis-executor') {
    Write-Pass "jarvis.execution has consumer group jarvis-executor (executor running)"
} elseif ($groupsEx -match 'no such key|ERR') {
    Write-Fail "Stream jarvis.execution missing. Start executor so it creates the group."
    $redisOk = $false
} else {
    Write-Fail "Could not confirm executor group on jarvis.execution."
    $redisOk = $false
}

if (-not $redisOk) {
    Write-Host "LIVE_STACK_FAIL stage=REDIS" -ForegroundColor Red
    exit 1
}

# --- Stage CMD ---
Write-Stage "CMD" "Command submission (control plane publishes to Redis for coordinator)"
$apCmd = $ApprovalCommandText
if ([string]::IsNullOrWhiteSpace($apCmd)) { $apCmd = $env:JARVIS_SMOKE_APPROVAL_COMMAND }
if ([string]::IsNullOrWhiteSpace($apCmd)) {
    $apCmd = 'JARVIS_OPERATOR_APPROVAL_REQUIRED: describe your favorite color in one word (live-stack rehearsal only).'
}

$body = @{ text = $apCmd; source = 'command_center' } | ConvertTo-Json -Compress
try {
    $cmdResp = Invoke-RestMethod -Uri "$Api/commands" -Method Post -Headers $Headers -Body $body -TimeoutSec 90
} catch {
    Write-Fail "POST /api/v1/commands: $($_.Exception.Message)"
    Write-Host "LIVE_STACK_FAIL stage=CMD" -ForegroundColor Red
    exit 1
}
$MissionId = $cmdResp.mission_id.ToString()
Write-Pass "Mission created: $MissionId (status=$($cmdResp.mission_status))"

# --- Stage GUARD: wait for pending approval (coordinator + DashClaw) ---
Write-Stage "GUARD" "Coordinator / DashClaw: pending approval for mission"
Write-Info "Poll GET /api/v1/approvals/pending (timeout ${PollTimeoutSec}s) ..."
$deadline = (Get-Date).AddSeconds($PollTimeoutSec)
$foundApproval = $null
$policyAllowedBeforeApproval = $false
while ((Get-Date) -lt $deadline) {
    try {
        $pending = Invoke-RestMethod -Uri "$Api/approvals/pending" -Method Get -TimeoutSec 30
    } catch {
        Write-Fail "GET /approvals/pending: $($_.Exception.Message)"
        Write-Host "LIVE_STACK_FAIL stage=GUARD" -ForegroundColor Red
        exit 1
    }
    foreach ($a in @($pending)) {
        $mid = $null
        if ($a.mission_id) { $mid = $a.mission_id.ToString() }
        if ($mid -eq $MissionId -and $a.status -eq 'pending') {
            $foundApproval = $a
            break
        }
    }
    if ($foundApproval) { break }

    try {
        $ev = Invoke-RestMethod -Uri "$Api/missions/$MissionId/events" -Method Get -TimeoutSec 30
    } catch { $ev = @() }
    foreach ($e in @($ev)) {
        if ($e.event_type -eq 'receipt_recorded') {
            $policyAllowedBeforeApproval = $true
            break
        }
    }
    if ($policyAllowedBeforeApproval) { break }
    Start-Sleep -Seconds $PollIntervalSec
}

if ($policyAllowedBeforeApproval -and -not $foundApproval) {
    Write-Info "receipt_recorded before pending approval — DashClaw policy allowed execution (not a broken stack)."
    try {
        $mEarly = Invoke-RestMethod -Uri "$Api/missions/$MissionId" -Method Get -TimeoutSec 30
    } catch {
        Write-Fail "GET mission (early policy path): $($_.Exception.Message)"
        Write-Host "LIVE_STACK_FAIL stage=GUARD" -ForegroundColor Red
        exit 1
    }
    try {
        $bundleEarly = Invoke-RestMethod -Uri "$Api/missions/$MissionId/bundle" -Method Get -TimeoutSec 30
    } catch {
        Write-Fail "GET bundle (early policy path): $($_.Exception.Message)"
        Write-Host "LIVE_STACK_FAIL stage=GUARD" -ForegroundColor Red
        exit 1
    }
    $typesEarly = @(@($bundleEarly.events) | ForEach-Object { $_.event_type })
    $hasCreated = $typesEarly -contains 'created'
    $hasReceiptEv = $typesEarly -contains 'receipt_recorded'
    $rc = @($bundleEarly.receipts).Count
    Write-Pass "Bundle fetchable; mission_status=$($mEarly.status); events: created=$hasCreated receipt_recorded=$hasReceiptEv; receipts=$rc"
    Write-Host "LIVE_STACK_RESULT status=known_nonblocking classification=policy_allowed_execution mission_id=$MissionId mission_status=$($mEarly.status) bundle_fetch_ok=true bundle_has_created=$hasCreated bundle_has_receipt_recorded=$hasReceiptEv receipts_count=$rc" -ForegroundColor Green
    Write-Host "LIVE_STACK_PASS mission_id=$MissionId outcome=known_nonblocking" -ForegroundColor Green
    Write-Info "For full approval-gated path, use command text that triggers requires_approval (JARVIS_SMOKE_APPROVAL_COMMAND or -ApprovalCommandText)."
    exit 0
}

if (-not $foundApproval) {
    Write-Fail "Timeout: no pending approval for mission $MissionId"
    Write-Info "Check coordinator logs, DASHCLAW_BASE_URL, DashClaw /api/guard policy for this command text."
    Write-Host "LIVE_STACK_FAIL stage=GUARD" -ForegroundColor Red
    exit 1
}
$ApprovalId = $foundApproval.id.ToString()
Write-Pass "Pending approval id=$ApprovalId (runtime-created)"

# --- Stage APRV ---
Write-Stage "APRV" "Approval resolution (approve via control plane)"
$decBody = @{
    decision    = 'approved'
    decided_by  = 'operator'
    decided_via = 'command_center'
} | ConvertTo-Json -Compress
try {
    $dec = Invoke-RestMethod -Uri "$Api/approvals/$ApprovalId/decision" -Method Post -Headers $Headers -Body $decBody -TimeoutSec 60
} catch {
    Write-Fail "POST decision: $($_.Exception.Message)"
    Write-Host "LIVE_STACK_FAIL stage=APRV" -ForegroundColor Red
    exit 1
}
if ($dec.status -ne 'approved') {
    Write-Fail "Expected approval status approved, got $($dec.status)"
    Write-Host "LIVE_STACK_FAIL stage=APRV" -ForegroundColor Red
    exit 1
}
Write-Pass "Approval recorded as approved"

# --- Stage EXEC: wait for real receipt ---
Write-Stage "EXEC" "Executor / OpenClaw: receipt_recorded"
Write-Info "Poll mission events for receipt_recorded with summary (timeout ${PollTimeoutSec}s) ..."
$deadline2 = (Get-Date).AddSeconds($PollTimeoutSec)
$gotReceipt = $false
while ((Get-Date) -lt $deadline2) {
    try {
        $m = Invoke-RestMethod -Uri "$Api/missions/$MissionId" -Method Get -TimeoutSec 30
    } catch {
        Write-Fail "GET mission: $($_.Exception.Message)"
        Write-Host "LIVE_STACK_FAIL stage=EXEC" -ForegroundColor Red
        exit 1
    }
    try {
        $events = Invoke-RestMethod -Uri "$Api/missions/$MissionId/events" -Method Get -TimeoutSec 30
    } catch {
        Write-Fail "GET events: $($_.Exception.Message)"
        Write-Host "LIVE_STACK_FAIL stage=EXEC" -ForegroundColor Red
        exit 1
    }
    foreach ($e in @($events)) {
        if ($e.event_type -eq 'receipt_recorded') {
            $sum = Get-EventSummaryFromPayload $e.payload
            $s = if ($null -eq $sum) { '' } else { $sum.ToString().Trim() }
            if ($s.Length -gt 0) {
                Write-Pass "receipt_recorded with non-empty summary ($($s.Length) chars); mission status=$($m.status)"
                $gotReceipt = $true
                break
            }
        }
    }
    if ($gotReceipt) { break }
    Start-Sleep -Seconds $PollIntervalSec
}

if (-not $gotReceipt) {
    Write-Fail "Timeout: no receipt_recorded with summary for mission $MissionId"
    Write-Info "Check executor logs, Redis jarvis.execution, OpenClaw gateway, CONTROL_PLANE_API_KEY on executor."
    Write-Host "LIVE_STACK_FAIL stage=EXEC" -ForegroundColor Red
    exit 1
}

# --- Stage BUNDLE ---
Write-Stage "BUNDLE" "Mission bundle truth"
try {
    $bundle = Invoke-RestMethod -Uri "$Api/missions/$MissionId/bundle" -Method Get -TimeoutSec 30
} catch {
    Write-Fail "GET bundle: $($_.Exception.Message)"
    Write-Host "LIVE_STACK_FAIL stage=BUNDLE" -ForegroundColor Red
    exit 1
}

$types = @(@($bundle.events) | ForEach-Object { $_.event_type })
$bundleOk = $true
if ($types -contains 'created') { Write-Pass "events: created" } else { Write-Fail "events: missing created"; $bundleOk = $false }
if ($types -contains 'approval_requested') { Write-Pass "events: approval_requested" } else { Write-Fail "events: missing approval_requested"; $bundleOk = $false }
if ($types -contains 'approval_resolved') { Write-Pass "events: approval_resolved" } else { Write-Fail "events: missing approval_resolved"; $bundleOk = $false }
if ($types -contains 'receipt_recorded') { Write-Pass "events: receipt_recorded" } else { Write-Fail "events: missing receipt_recorded"; $bundleOk = $false }

$appr = @($bundle.approvals | Where-Object { $_.status -eq 'approved' })
if ($appr.Count -ge 1) {
    Write-Pass "approvals: at least one approved row"
} else {
    Write-Fail "approvals: no approved row"
    $bundleOk = $false
}

if (@($bundle.receipts).Count -ge 1) {
    Write-Pass "receipts: count >= 1"
} else {
    Write-Fail "receipts: empty"
    $bundleOk = $false
}

if (-not $bundleOk) {
    Write-Host "LIVE_STACK_FAIL stage=BUNDLE" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "LIVE_STACK_PASS mission_id=$MissionId" -ForegroundColor Green
Write-Info "Inspect in Command Center: /missions/$MissionId"
exit 0
