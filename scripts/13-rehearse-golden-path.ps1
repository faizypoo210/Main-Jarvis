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
#>
param(
    [string]$ControlPlaneUrl = ""
)

$ErrorActionPreference = 'Stop'
$script:FailCount = 0

function Write-Stage($m) { Write-Host "" ; Write-Host "=== $m ===" -ForegroundColor Cyan }
function Write-Pass($m) { Write-Host "[PASS] $m" -ForegroundColor Green }
function Write-Fail($m) { Write-Host "[FAIL] $m" -ForegroundColor Red; $script:FailCount++ }
function Write-Info($m) { Write-Host "       $m" -ForegroundColor DarkGray }

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

$Base = Get-CpBase -Url $ControlPlaneUrl
$Api = "$Base/api/v1"
$ApiKey = Get-ApiKey

Write-Host ""
Write-Host "Jarvis golden-path rehearsal (control plane authority)" -ForegroundColor White
Write-Host "Base: $Base" -ForegroundColor DarkGray

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Fail "CONTROL_PLANE_API_KEY is not set (mutations require x-api-key)."
    Write-Info "Set User env CONTROL_PLANE_API_KEY or pass JARVIS_SMOKE_API_KEY."
    exit 1
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
    exit 1
}

# --- Stage B: command to mission ---
Write-Stage "B - Command intake (mission created)"
$cmdText = 'Golden path rehearsal: acknowledge with a brief status only.'
$cmdBody = @{ text = $cmdText; source = 'command_center' } | ConvertTo-Json -Compress
try {
    $cmdResp = Invoke-RestMethod -Uri "$Api/commands" -Method Post -Headers $Headers -Body $cmdBody -TimeoutSec 60
}
catch {
    Write-Fail ('POST /api/v1/commands failed: ' + $_.Exception.Message)
    exit 1
}
$MissionId = $cmdResp.mission_id.ToString()
Write-Pass "POST /api/v1/commands - mission_id=$MissionId status=$($cmdResp.mission_status)"

# --- Stage C: request approval (governed path) ---
Write-Stage "C - Approval requested (POST /approvals)"
$apBody = @{
    mission_id   = $MissionId
    action_type  = 'Rehearsal execution step'
    risk_class   = 'amber'
    reason       = 'Operator rehearsal - confirm before synthetic completion.'
    requested_by = 'golden_path_rehearsal'
    requested_via = 'command_center'
} | ConvertTo-Json -Compress

try {
    $ap = Invoke-RestMethod -Uri "$Api/approvals" -Method Post -Headers $Headers -Body $apBody -TimeoutSec 60
}
catch {
    Write-Fail ('POST /api/v1/approvals failed: ' + $_.Exception.Message)
    exit 1
}
$ApprovalId = $ap.id.ToString()
if ($ap.status -ne 'pending') { Write-Fail "New approval should be pending" }
else { Write-Pass "POST /api/v1/approvals - approval_id=$ApprovalId pending" }

# --- Stage D: pending list contains this mission ---
Write-Stage "D - Pending approvals list"
try {
    $pending = Invoke-RestMethod -Uri "$Api/approvals/pending" -Method Get -TimeoutSec 30
}
catch {
    Write-Fail ('GET /api/v1/approvals/pending failed: ' + $_.Exception.Message)
    exit 1
}
$match = @($pending) | Where-Object { $_.mission_id.ToString() -eq $MissionId -and $_.status -eq 'pending' }
if ($match.Count -ge 1) {
    Write-Pass "GET /approvals/pending includes mission (at least one pending row)"
}
else {
    Write-Fail "Pending list missing mission $MissionId"
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
    Write-Fail ('POST /api/v1/approvals/{id}/decision failed: ' + $_.Exception.Message)
    exit 1
}
if ($dec.status -eq 'approved') {
    Write-Pass "Decision recorded - approval status=approved"
}
else {
    Write-Fail "Expected approval status approved, got $($dec.status)"
}

# --- Stage F: mission active ---
Write-Stage "F - Mission resumed (active)"
Start-Sleep -Milliseconds 400
try {
    $m = Invoke-RestMethod -Uri "$Api/missions/$MissionId" -Method Get -TimeoutSec 30
}
catch {
    Write-Fail ('GET /api/v1/missions/{id} failed: ' + $_.Exception.Message)
    exit 1
}
if ($m.status -ne 'active') {
    Write-Fail "Mission status should be active after approve, got $($m.status)"
    exit 1
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
    Write-Fail ('POST /api/v1/receipts failed: ' + $_.Exception.Message)
    exit 1
}
Write-Pass "POST /api/v1/receipts - receipt_id=$($rc.id)"

# --- Stage H: bundle coherence ---
Write-Stage "H - Mission bundle verification"
try {
    $bundle = Invoke-RestMethod -Uri "$Api/missions/$MissionId/bundle" -Method Get -TimeoutSec 30
}
catch {
    Write-Fail ('GET /api/v1/missions/{id}/bundle failed: ' + $_.Exception.Message)
    exit 1
}

$evs = @($bundle.events)
$types = @($evs | ForEach-Object { $_.event_type })
$hasCreated = $types -contains 'created'
$hasApReq = $types -contains 'approval_requested'
$hasApRes = $types -contains 'approval_resolved'
$hasRcpt = $types -contains 'receipt_recorded'

if ($hasCreated) { Write-Pass "Events include created" } else { Write-Fail "Events missing created" }
if ($hasApReq) { Write-Pass "Events include approval_requested" } else { Write-Fail "Events missing approval_requested" }
if ($hasApRes) { Write-Pass "Events include approval_resolved" } else { Write-Fail "Events missing approval_resolved" }
if ($hasRcpt) { Write-Pass "Events include receipt_recorded" } else { Write-Fail "Events missing receipt_recorded" }

$appr = @($bundle.approvals)
$approvedRows = @($appr | Where-Object { $_.status -eq 'approved' })
if ($approvedRows.Count -ge 1) {
    Write-Pass "Bundle approvals include at least one approved row"
}
else {
    Write-Fail "Bundle approvals missing approved row"
}

$recs = @($bundle.receipts)
if ($recs.Count -ge 1) {
    Write-Pass "Bundle receipts count >= 1"
}
else {
    Write-Fail "Bundle receipts empty"
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
    exit 0
}
Write-Host "GOLDEN_PATH_REHEARSAL_FAIL failures=$($script:FailCount)" -ForegroundColor Red
exit 1
