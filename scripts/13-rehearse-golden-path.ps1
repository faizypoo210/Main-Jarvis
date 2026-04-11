#Requires -Version 5.1
<#
.SYNOPSIS
  Golden-path operator rehearsal — control plane APIs only (no coordinator bypass).

.DESCRIPTION
  Stages:
    1) POST /api/v1/commands — mission created
    2) POST /api/v1/approvals — governance request (same API as coordinator)
    3) Verify pending approval exists for mission
    4) POST /api/v1/approvals/{id}/decision — approve
    5) Verify mission active
    6) POST /api/v1/receipts — execution receipt (same API as executor)
    7) GET /api/v1/missions/{id}/bundle — coherence check

  Requires: CONTROL_PLANE_URL (default http://127.0.0.1:8001), CONTROL_PLANE_API_KEY for mutating routes.
  Non-destructive: creates normal mission/approval/receipt rows only.

.PARAMETER ControlPlaneUrl
  Base URL without trailing slash.
.PARAMETER SkipRedisIsolationVerify
  Do not compare XLEN on jarvis.commands before/after the synthetic command (default: verify when Redis is reachable).
.PARAMETER RedisContainer
  Docker Redis container name for redis-cli via docker exec (default jarvis-redis).
#>
param(
    [string]$ControlPlaneUrl = "",
    [switch]$SkipRedisIsolationVerify,
    [string]$RedisContainer = "jarvis-redis"
)

$ApLib = Join-Path $PSScriptRoot 'lib\ApprovalPayloadContract.ps1'
if (-not (Test-Path -LiteralPath $ApLib)) { throw "Missing $ApLib" }
. $ApLib

$ErrorActionPreference = 'Stop'
$script:FailCount = 0
$script:HasContractDrift = $false

function Write-Stage($m) { Write-Host "" ; Write-Host "=== $m ===" -ForegroundColor Cyan }
function Write-Pass($m) { Write-Host "[PASS] $m" -ForegroundColor Green }
function Write-Fail {
    param([string]$m, [switch]$ContractDrift)
    Write-Host "[FAIL] $m" -ForegroundColor Red
    $script:FailCount++
    if ($ContractDrift) { $script:HasContractDrift = $true }
}
function Write-Info($m) { Write-Host "       $m" -ForegroundColor DarkGray }

function Get-RestErrorDetails {
    param($ErrorRecord)
    $status = $null
    $body = $null
    $msg = $ErrorRecord.Exception.Message
    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
        $body = $ErrorRecord.ErrorDetails.Message.Trim()
    }
    $ex = $ErrorRecord.Exception
    if ($null -ne $ex.Response) {
        $resp = $ex.Response
        try {
            if ($resp -is [System.Net.Http.HttpResponseMessage]) {
                $status = [int]$resp.StatusCode
                if ([string]::IsNullOrWhiteSpace($body) -and $null -ne $resp.Content) {
                    $body = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                }
            }
            else {
                $sc = $resp.StatusCode
                if ($null -ne $sc) {
                    if ($sc -is [int]) { $status = $sc }
                    else { $status = [int]$sc }
                }
                if ([string]::IsNullOrWhiteSpace($body)) {
                    $stream = $resp.GetResponseStream()
                    if ($null -ne $stream) {
                        $reader = New-Object System.IO.StreamReader($stream)
                        $body = $reader.ReadToEnd()
                    }
                }
            }
        }
        catch {}
    }
    if ($null -eq $status -and $msg -match '\((\d{3})\)') { $status = [int]$Matches[1] }
    if ($null -eq $status -and $msg -match '422') { $status = 422 }
    if ($null -eq $status -and $msg -match '401') { $status = 401 }
    if ($null -eq $status -and $msg -match '404') { $status = 404 }
    return @{ StatusCode = $status; Body = $body; Message = $msg }
}

function Write-GoldenPathSyntheticClassLine {
    $class = if ($script:FailCount -eq 0) {
        'pass'
    }
    elseif ($script:HasContractDrift) {
        'contract_drift'
    }
    else {
        'precondition_fail'
    }
    Write-Host "GOLDEN_PATH_SYNTHETIC_CLASS=$class"
}

function Exit-GoldenPath {
    param([int]$Code)
    Write-GoldenPathSyntheticClassLine
    exit $Code
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

function Get-JarvisCommandsStreamLength {
    $out = Invoke-RedisCli -RedisArgs @('XLEN', 'jarvis.commands')
    if ($null -eq $out) { return $null }
    $trim = $out.Trim()
    if ($trim -match '^(\d+)\s*$') { return [long]$Matches[1] }
    if ($trim -match '^ERR') { return $null }
    if ($trim -match '(\d+)') { return [long]$Matches[1] }
    return $null
}

$Base = Get-CpBase -Url $ControlPlaneUrl
$Api = "$Base/api/v1"
$ApiKey = Get-ApiKey

Write-Host ""
Write-Host "Jarvis golden-path rehearsal (control plane authority)" -ForegroundColor White
Write-Host "Base: $Base" -ForegroundColor DarkGray

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Fail "CONTROL_PLANE_API_KEY is not set (mutations require x-api-key)."
    Write-Info "Set User env CONTROL_PLANE_API_KEY or pass JARVIS_SMOKE_API_KEY."
    Exit-GoldenPath 1
}

$Headers = @{
    'x-api-key'    = $ApiKey
    'Content-Type' = 'application/json; charset=utf-8'
}

# --- Stage A: health ---
Write-Stage "A - Control plane health"
try {
    $h = Invoke-RestMethod -Uri "$Base/health" -Method Get -TimeoutSec 15
    if ($h.status -eq 'ok') { Write-Pass "GET /health" } else { Write-Fail "GET /health unexpected body" }
}
catch {
    Write-Fail ('GET /health failed: ' + $_.Exception.Message)
    Exit-GoldenPath 1
}

# --- Stage B: command to mission ---
Write-Stage "B - Command intake (mission created)"
$cmdText = 'Golden path rehearsal: acknowledge with a brief status only.'
# Isolate from Redis/coordinator: control plane skips jarvis.commands publish when both markers are set (see command_service.py).
$cmdBody = @{
    text    = $cmdText
    source  = 'command_center'
    context = @{
        rehearsal_mode       = 'synthetic_api_only'
        skip_runtime_publish = $true
    }
} | ConvertTo-Json -Compress -Depth 6

$redisLenBefore = $null
if (-not $SkipRedisIsolationVerify) {
    $redisLenBefore = Get-JarvisCommandsStreamLength
    if ($null -eq $redisLenBefore) {
        Write-Info "[SKIP] Redis jarvis.commands XLEN unavailable — isolation verify skipped (not a failure)."
    } else {
        Write-Info "Redis jarvis.commands XLEN before POST /commands: $redisLenBefore"
    }
}

try {
    $cmdResp = Invoke-RestMethod -Uri "$Api/commands" -Method Post -Headers $Headers -Body $cmdBody -TimeoutSec 60
}
catch {
    $info = Get-RestErrorDetails -ErrorRecord $_
    if ($null -ne $info.StatusCode -and ($info.StatusCode -eq 422 -or $info.StatusCode -eq 400)) {
        $script:HasContractDrift = $true
    }
    $detail = if ($info.Body) { $info.Body } else { $info.Message }
    if ($detail.Length -gt 1200) { $detail = $detail.Substring(0, 1200) + '...' }
    Write-Fail "POST /api/v1/commands failed: HTTP $($info.StatusCode) $detail"
    if ($info.Body -and $info.Body.Length -lt 2000) { Write-Info "Response body: $($info.Body)" }
    Exit-GoldenPath 1
}
$MissionId = $cmdResp.mission_id.ToString()
Write-Pass "POST /api/v1/commands - mission_id=$MissionId status=$($cmdResp.mission_status)"

if (-not $SkipRedisIsolationVerify -and ($null -ne $redisLenBefore)) {
    $redisLenAfter = Get-JarvisCommandsStreamLength
    if ($null -eq $redisLenAfter) {
        Write-Info "[SKIP] Redis XLEN after command unavailable — compare skipped."
    } elseif ($redisLenAfter -eq $redisLenBefore) {
        Write-Pass "Redis jarvis.commands length unchanged (synthetic isolation verified; no coordinator publish)"
    } else {
        Write-Fail "Redis jarvis.commands length changed ($redisLenBefore -> $redisLenAfter); expected no XADD for synthetic rehearsal. If another process published to the stream, retry or use -SkipRedisIsolationVerify."
    }
}

# --- Stage C: request approval (governed path) ---
Write-Stage "C - Approval requested (POST /approvals)"
$apBodyObj = New-SyntheticApprovalCreatePayload `
    -MissionId $MissionId `
    -CommandText $cmdText `
    -ActionType 'Rehearsal execution step' `
    -Reason 'Operator rehearsal - confirm before synthetic completion.' `
    -RequestedBy 'golden_path_rehearsal' `
    -RequestedVia 'command_center' `
    -RiskClass 'amber'
$apValidate = Test-ApprovalCreatePayload -Payload $apBodyObj
if (-not $apValidate.Valid) {
    $script:HasContractDrift = $true
    Write-Fail "Approval payload failed local validation (contract drift before POST): $($apValidate.Errors -join '; ')"
    Write-Info $apValidate.ContractRef
    Exit-GoldenPath 1
}
$apBody = ConvertTo-ApprovalCreateJson -Payload $apBodyObj

try {
    $ap = Invoke-RestMethod -Uri "$Api/approvals" -Method Post -Headers $Headers -Body $apBody -TimeoutSec 60
}
catch {
    $info = Get-RestErrorDetails -ErrorRecord $_
    if ($null -ne $info.StatusCode -and ($info.StatusCode -eq 422 -or $info.StatusCode -eq 400)) {
        $script:HasContractDrift = $true
    }
    $detail = if ($info.Body) { $info.Body } else { $info.Message }
    if ($detail.Length -gt 1200) { $detail = $detail.Substring(0, 1200) + '...' }
    Write-Fail "POST /api/v1/approvals failed: HTTP $($info.StatusCode) $detail"
    if ($info.StatusCode -eq 422) {
        Write-Info "422: ApprovalCreate contract drift (server rejected body). Compare scripts/lib/ApprovalPayloadContract.ps1 with services/control-plane/app/schemas/approvals.py; requested_via must be voice|command_center|system|sms."
    }
    if ($info.StatusCode -eq 401) {
        Write-Info "401: x-api-key must match server CONTROL_PLANE_API_KEY when auth is enabled."
    }
    if ($info.StatusCode -eq 404) {
        Write-Info "404: mission not found for approval (wrong base URL or stale mission_id)."
    }
    if ($info.Body -and $info.Body.Length -lt 2500) { Write-Info "Response body: $($info.Body)" }
    Exit-GoldenPath 1
}
$ApprovalId = $ap.id.ToString()
if ($ap.status -ne 'pending') { Write-Fail "New approval should be pending" -ContractDrift }
else { Write-Pass "POST /api/v1/approvals - approval_id=$ApprovalId pending" }

# --- Stage D: pending list contains this mission ---
Write-Stage "D - Pending approvals list"
try {
    $pending = Invoke-RestMethod -Uri "$Api/approvals/pending" -Method Get -TimeoutSec 30
}
catch {
    $info = Get-RestErrorDetails -ErrorRecord $_
    if ($null -ne $info.StatusCode -and ($info.StatusCode -eq 422 -or $info.StatusCode -eq 400)) {
        $script:HasContractDrift = $true
    }
    $detail = if ($info.Body) { $info.Body } else { $info.Message }
    Write-Fail "GET /api/v1/approvals/pending failed: HTTP $($info.StatusCode) $detail"
    Exit-GoldenPath 1
}
$match = @($pending) | Where-Object { $_.mission_id.ToString() -eq $MissionId -and $_.status -eq 'pending' }
if ($match.Count -ge 1) {
    Write-Pass "GET /approvals/pending includes mission (at least one pending row)"
}
else {
    Write-Fail "Pending list missing mission $MissionId" -ContractDrift
}

# --- Stage E: approve ---
Write-Stage "E - Approval resolution (approve)"
$decBody = @{
    decision     = 'approved'
    decided_by   = 'operator'
    decided_via  = 'command_center'
} | ConvertTo-Json -Compress
try {
    $dec = Invoke-RestMethod -Uri "$Api/approvals/$ApprovalId/decision" -Method Post -Headers $Headers -Body $decBody -TimeoutSec 60
}
catch {
    $info = Get-RestErrorDetails -ErrorRecord $_
    if ($null -ne $info.StatusCode -and ($info.StatusCode -eq 422 -or $info.StatusCode -eq 400)) {
        $script:HasContractDrift = $true
    }
    $detail = if ($info.Body) { $info.Body } else { $info.Message }
    Write-Fail "POST /api/v1/approvals/{id}/decision failed: HTTP $($info.StatusCode) $detail"
    if ($info.Body -and $info.Body.Length -lt 2000) { Write-Info "Response body: $($info.Body)" }
    Exit-GoldenPath 1
}
if ($dec.status -eq 'approved') {
    Write-Pass "Decision recorded - approval status=approved"
}
else {
    Write-Fail "Expected approval status approved, got $($dec.status)" -ContractDrift
}

# --- Stage F: mission active ---
Write-Stage "F - Mission resumed (active)"
Start-Sleep -Milliseconds 400
try {
    $m = Invoke-RestMethod -Uri "$Api/missions/$MissionId" -Method Get -TimeoutSec 30
}
catch {
    $info = Get-RestErrorDetails -ErrorRecord $_
    if ($null -ne $info.StatusCode -and ($info.StatusCode -eq 422 -or $info.StatusCode -eq 400)) {
        $script:HasContractDrift = $true
    }
    $detail = if ($info.Body) { $info.Body } else { $info.Message }
    Write-Fail "GET /api/v1/missions/{id} failed: HTTP $($info.StatusCode) $detail"
    Exit-GoldenPath 1
}
if ($m.status -ne 'active') {
    Write-Fail "Mission status should be active after approve, got $($m.status)" -ContractDrift
    Exit-GoldenPath 1
}
Write-Pass "Mission status is active"

# --- Stage G: receipt (executor-shaped) ---
Write-Stage "G - Receipt recorded"
$rcBody = @{
    mission_id    = $MissionId
    receipt_type  = 'execution'
    source        = 'golden_path_rehearsal'
    summary       = 'Rehearsal run finished; bundle should list this receipt.'
    payload       = @{
        execution_meta = @{
            lane                  = 'rehearsal'
            model                 = 'n/a'
            resumed_from_approval = $true
        }
    }
} | ConvertTo-Json -Compress -Depth 6

try {
    $rc = Invoke-RestMethod -Uri "$Api/receipts" -Method Post -Headers $Headers -Body $rcBody -TimeoutSec 60
}
catch {
    $info = Get-RestErrorDetails -ErrorRecord $_
    if ($null -ne $info.StatusCode -and ($info.StatusCode -eq 422 -or $info.StatusCode -eq 400)) {
        $script:HasContractDrift = $true
    }
    $detail = if ($info.Body) { $info.Body } else { $info.Message }
    Write-Fail "POST /api/v1/receipts failed: HTTP $($info.StatusCode) $detail"
    if ($info.Body -and $info.Body.Length -lt 2000) { Write-Info "Response body: $($info.Body)" }
    Exit-GoldenPath 1
}
Write-Pass "POST /api/v1/receipts - receipt_id=$($rc.id)"

# --- Stage H: bundle coherence ---
Write-Stage "H - Mission bundle verification"
try {
    $bundle = Invoke-RestMethod -Uri "$Api/missions/$MissionId/bundle" -Method Get -TimeoutSec 30
}
catch {
    $info = Get-RestErrorDetails -ErrorRecord $_
    if ($null -ne $info.StatusCode -and ($info.StatusCode -eq 422 -or $info.StatusCode -eq 400)) {
        $script:HasContractDrift = $true
    }
    $detail = if ($info.Body) { $info.Body } else { $info.Message }
    Write-Fail "GET /api/v1/missions/{id}/bundle failed: HTTP $($info.StatusCode) $detail"
    Exit-GoldenPath 1
}

$evs = @($bundle.events)
$types = @($evs | ForEach-Object { $_.event_type })
$hasCreated = $types -contains 'created'
$hasApReq = $types -contains 'approval_requested'
$hasApRes = $types -contains 'approval_resolved'
$hasRcpt = $types -contains 'receipt_recorded'

if ($hasCreated) { Write-Pass "Events include created" } else { Write-Fail "Events missing created" -ContractDrift }
if ($hasApReq) { Write-Pass "Events include approval_requested" } else { Write-Fail "Events missing approval_requested" -ContractDrift }
if ($hasApRes) { Write-Pass "Events include approval_resolved" } else { Write-Fail "Events missing approval_resolved" -ContractDrift }
if ($hasRcpt) { Write-Pass "Events include receipt_recorded" } else { Write-Fail "Events missing receipt_recorded" -ContractDrift }

$appr = @($bundle.approvals)
$approvedRows = @($appr | Where-Object { $_.status -eq 'approved' })
if ($approvedRows.Count -ge 1) {
    Write-Pass "Bundle approvals include at least one approved row"
}
else {
    Write-Fail "Bundle approvals missing approved row" -ContractDrift
}

$recs = @($bundle.receipts)
if ($recs.Count -ge 1) {
    Write-Pass "Bundle receipts count >= 1"
}
else {
    Write-Fail "Bundle receipts empty" -ContractDrift
}

$metaOk = $false
foreach ($r in $recs) {
    if ($null -eq $r.payload) { continue }
    if ($null -ne $r.payload.execution_meta) {
        $metaOk = $true
        break
    }
}
if ($metaOk) {
    Write-Pass "Receipt payload includes execution_meta"
}
else {
    Write-Info "Optional: execution_meta not present on receipt payload"
}

# --- Summary ---
Write-Host ""
if ($script:FailCount -eq 0) {
    Write-Host "GOLDEN_PATH_REHEARSAL_PASS mission_id=$MissionId" -ForegroundColor Green
    Write-Host "Open Command Center: /missions/$MissionId" -ForegroundColor DarkGray
    Exit-GoldenPath 0
}
Write-Host "GOLDEN_PATH_REHEARSAL_FAIL failures=$($script:FailCount)" -ForegroundColor Red
Exit-GoldenPath 1
