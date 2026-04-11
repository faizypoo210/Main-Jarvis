#Requires -Version 5.1
<#
.SYNOPSIS
  End-to-end smoke test for the canonical Jarvis stack (Control Plane → Redis → Coordinator → Executor → OpenClaw → receipt).

.DESCRIPTION
  Happy path (default): POST /api/v1/commands, then poll until mission_events contains receipt_recorded with non-empty payload.summary.

  Approval path (-ApprovalPath): POST a command intended to trigger DashClaw requires_approval, then verify a pending Approval row exists for that mission_id. Does not approve or deny.

  Prerequisites: jarvis.ps1 (or equivalent) running - control plane :8001, Redis, Postgres, coordinator (DashClaw env), executor, OpenClaw gateway. Safe, reversible: only creates missions and receipts like normal operator traffic.

.PARAMETER ApprovalPath
  Run approval verification instead of receipt happy path.

.PARAMETER ControlPlaneUrl
  Override; default CONTROL_PLANE_URL or http://localhost:8001

.PARAMETER CommandText
  Happy-path command text (must be allowed by your DashClaw guard). Default is a minimal safe prompt.

.PARAMETER ApprovalCommandText
  Command text for -ApprovalPath (should trigger requires_approval in DashClaw). Default from JARVIS_SMOKE_APPROVAL_COMMAND or a documented placeholder.

.PARAMETER PollTimeoutSec
  Max wait for async pipeline (default 240).

.PARAMETER PollIntervalSec
  Poll interval for mission events / approvals (default 2).
#>
param(
    [switch]$ApprovalPath,
    [string]$ControlPlaneUrl = "",
    [string]$CommandText = "",
    [string]$ApprovalCommandText = "",
    [int]$PollTimeoutSec = 240,
    [int]$PollIntervalSec = 2
)

$ErrorActionPreference = 'Stop'

function Write-Step($m) { Write-Host $m -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Write-Bad($m)  { Write-Host "[FAIL] $m" -ForegroundColor Red }
function Write-Info($m) { Write-Host "[INFO] $m" -ForegroundColor DarkGray }

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
    if ([string]::IsNullOrWhiteSpace($u)) { $u = 'http://localhost:8001' }
    return $u.TrimEnd('/')
}

function Test-ControlPlaneHealth {
    param([string]$Base)
    try {
        $r = Invoke-WebRequest -Uri "$Base/health" -UseBasicParsing -TimeoutSec 15
        if ($r.StatusCode -ne 200) {
            Write-Bad "Control plane /health returned HTTP $($r.StatusCode). Is the API running on $Base ?"
            return $false
        }
        Write-Ok "Control plane /health (8001)"
        return $true
    } catch {
        Write-Bad "Control plane unreachable at $Base/health : $_"
        Write-Info "Start control plane: cd services\control-plane && uvicorn app.main:app --host 0.0.0.0 --port 8001"
        return $false
    }
}

function Test-PostgresDocker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Info "docker not in PATH; skipping Postgres container check."
        return $true
    }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        $out = docker exec jarvis-postgres pg_isready -U jarvis -d jarvis_missions 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Write-Bad "Postgres (jarvis-postgres) not ready: $out"
            return $false
        }
        Write-Ok "PostgreSQL jarvis_missions (pg_isready)"
        return $true
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-RedisDocker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Info "docker not in PATH; skipping Redis container check."
        return $true
    }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        $out = docker exec jarvis-redis redis-cli PING 2>&1 | Out-String
        if ($out -notmatch 'PONG') {
            Write-Bad "Redis (jarvis-redis) did not PONG: $out"
            return $false
        }
        Write-Ok "Redis PING (jarvis-redis)"
        return $true
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-Ollama {
    try {
        $r = Invoke-WebRequest -Uri 'http://localhost:11434' -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -ne 200) {
            Write-Host "[WARN] Ollama HTTP on 11434 returned $($r.StatusCode) - optional for this E2E (executor uses OpenClaw)." -ForegroundColor Yellow
            return $true
        }
        Write-Ok "Ollama HTTP (11434)"
        return $true
    } catch {
        Write-Host "[WARN] Ollama not reachable on 11434 - optional for this E2E (executor uses OpenClaw). $_" -ForegroundColor Yellow
        return $true
    }
}

function Test-OpenClawCli {
    if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
        Write-Bad "openclaw CLI not found on PATH."
        Write-Info "Install OpenClaw Gateway / CLI; see Phase 3 scripts."
        return $false
    }
    $out = & openclaw status 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Bad "openclaw status exited $($LASTEXITCODE). Output: $out"
        return $false
    }
    Write-Ok "openclaw status"
    return $true
}

function Test-DashClawOptional {
    $u = $env:DASHCLAW_BASE_URL
    if ([string]::IsNullOrWhiteSpace($u)) {
        Write-Info "DASHCLAW_BASE_URL not set in this shell. Coordinator loads its own process env - ensure coordinator/.env or User env has DASHCLAW_BASE_URL and DASHCLAW_API_KEY."
        return $true
    }
    try {
        $r = Invoke-WebRequest -Uri $u.TrimEnd('/') -UseBasicParsing -TimeoutSec 12
        Write-Ok "DashClaw base URL responded (HTTP $($r.StatusCode))"
        return $true
    } catch {
        Write-Bad "DashClaw not reachable at $u - coordinator cannot call /api/guard. $_"
        return $false
    }
}

function Get-EventSummary {
    param($Payload)
    if ($null -eq $Payload) { return $null }
    if ($Payload -is [hashtable]) {
        return $Payload['summary']
    }
    try {
        return $Payload.summary
    } catch {
        return $null
    }
}

function Invoke-SmokePreflight {
    # Returns $true if all required checks pass
    $ok = $true
    if (-not (Test-ControlPlaneHealth $script:Base)) { $ok = $false }
    if (-not (Test-PostgresDocker)) { $ok = $false }
    if (-not (Test-RedisDocker)) { $ok = $false }
    if (-not (Test-Ollama)) { $ok = $false }
    if (-not (Test-OpenClawCli)) { $ok = $false }
    if (-not (Test-DashClawOptional)) { $ok = $false }
    return $ok
}

# --- main ---
$script:Base = Get-CpBase -Url $ControlPlaneUrl
$apiKey = Get-ApiKey
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Bad "CONTROL_PLANE_API_KEY (or JARVIS_SMOKE_API_KEY) is not set. The smoke test must POST /api/v1/commands with x-api-key."
    exit 1
}

$headers = @{
    'x-api-key'    = $apiKey
    'Content-Type' = 'application/json; charset=utf-8'
}

Write-Step "=== JARVIS Phase 9: E2E smoke ($(
    if ($ApprovalPath) { 'approval path' } else { 'happy path' }
)) ==="

if (-not (Invoke-SmokePreflight)) {
    Write-Bad "Preflight failed. Fix the issues above before retrying."
    exit 1
}

if ($ApprovalPath) {
    # --- Approval path: pending approval row, no auto-approve ---
    $apCmd = $ApprovalCommandText
    if ([string]::IsNullOrWhiteSpace($apCmd)) {
        $apCmd = $env:JARVIS_SMOKE_APPROVAL_COMMAND
    }
    if ([string]::IsNullOrWhiteSpace($apCmd)) {
        $apCmd = 'JARVIS_OPERATOR_APPROVAL_REQUIRED: describe your favorite color in one word (smoke test only).'
    }

    $body = @{ text = $apCmd; source = 'api' } | ConvertTo-Json -Compress
    Write-Step "POST /api/v1/commands (approval trigger) ..."
    try {
        $cmdResp = Invoke-RestMethod -Uri "$script:Base/api/v1/commands" -Method Post -Headers $headers -Body $body -TimeoutSec 60
    } catch {
        Write-Bad "POST commands failed: $_"
        exit 1
    }
    $missionId = $cmdResp.mission_id
    Write-Ok "Mission created: $missionId"
    Write-Info "Polling GET /api/v1/approvals/pending for mission_id=$missionId (timeout ${PollTimeoutSec}s) ..."

    $deadline = (Get-Date).AddSeconds($PollTimeoutSec)
    $found = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $pending = Invoke-RestMethod -Uri "$script:Base/api/v1/approvals/pending" -Method Get -TimeoutSec 30
        } catch {
            Write-Bad "GET approvals/pending failed: $_"
            exit 1
        }
        $rows = @($pending)
        foreach ($a in $rows) {
            $mid = $null
            if ($a.mission_id) { $mid = $a.mission_id.ToString() }
            if ($mid -eq $missionId.ToString() -and ($a.status -eq 'pending')) {
                Write-Ok "Pending approval found (id=$($a.id)) for mission $missionId"
                $found = $true
                break
            }
        }
        if ($found) { break }

        $ev = Invoke-RestMethod -Uri "$script:Base/api/v1/missions/$missionId/events" -Method Get -TimeoutSec 30
        foreach ($e in @($ev)) {
            if ($e.event_type -eq 'receipt_recorded') {
                Write-Bad "Receipt already recorded (receipt_recorded). DashClaw allowed execution; use -ApprovalCommandText / JARVIS_SMOKE_APPROVAL_COMMAND so guard returns requires_approval."
                exit 1
            }
        }
        Start-Sleep -Seconds $PollIntervalSec
    }

    if (-not $found) {
        Write-Bad "Timeout: no pending approval for mission $missionId ."
        Write-Info "Coordinator must call DashClaw /api/guard and receive requires_approval (or unknown decision maps to requires_approval). Check coordinator logs, DASHCLAW_* env, and DashClaw rules for this command text."
        exit 1
    }

    Write-Host ""
    Write-Host "SMOKE_E2E_PASS approval_path=1 mission_id=$missionId (no approval decision was sent - safe)."
    exit 0
}

# --- Happy path: receipt_recorded.summary ---
$cmd = $CommandText
if ([string]::IsNullOrWhiteSpace($cmd)) {
    $cmd = $env:JARVIS_SMOKE_COMMAND_TEXT
}
if ([string]::IsNullOrWhiteSpace($cmd)) {
    $cmd = 'E2E smoke (safe): Reply with exactly the single word: JARVIS_OK'
}

$body = @{ text = $cmd; source = 'api' } | ConvertTo-Json -Compress
Write-Step "POST /api/v1/commands ..."
try {
    $cmdResp = Invoke-RestMethod -Uri "$script:Base/api/v1/commands" -Method Post -Headers $headers -Body $body -TimeoutSec 60
} catch {
    Write-Bad "POST commands failed: $_"
    exit 1
}
$missionId = $cmdResp.mission_id
Write-Ok "Mission created: $missionId"
Write-Info "Waiting for pipeline: Redis jarvis.commands → coordinator (DashClaw) → jarvis.execution → executor (OpenClaw) → POST receipts → receipt_recorded event ..."

$deadline = (Get-Date).AddSeconds($PollTimeoutSec)
while ((Get-Date) -lt $deadline) {
    try {
        $m = Invoke-RestMethod -Uri "$script:Base/api/v1/missions/$missionId" -Method Get -TimeoutSec 30
    } catch {
        Write-Bad "GET mission failed: $_"
        exit 1
    }
    if ($m.status -eq 'awaiting_approval') {
        Write-Bad "Mission is awaiting_approval. DashClaw did not allow; happy path blocked."
        Write-Info "Use a shorter/low-risk command or set JARVIS_SMOKE_COMMAND_TEXT / configure DashClaw to allow this text. Or run -ApprovalPath with a command that requires approval."
        exit 1
    }

    try {
        $events = Invoke-RestMethod -Uri "$script:Base/api/v1/missions/$missionId/events" -Method Get -TimeoutSec 30
    } catch {
        Write-Bad "GET events failed: $_"
        exit 1
    }
    foreach ($e in @($events)) {
        if ($e.event_type -eq 'approval_requested') {
            Write-Bad "Event approval_requested present - DashClaw required approval for this command."
            Write-Info "Adjust JARVIS_SMOKE_COMMAND_TEXT or DashClaw guard rules so this command is allowed."
            exit 1
        }
        if ($e.event_type -eq 'receipt_recorded') {
            $sum = Get-EventSummary $e.payload
            $s = if ($null -eq $sum) { '' } else { $sum.ToString().Trim() }
            if ($s.Length -gt 0) {
                Write-Ok "receipt_recorded with non-empty summary ($($s.Length) chars)"
                Write-Info "Mission status: $($m.status)"
                Write-Host ""
                Write-Host "SMOKE_E2E_PASS receipt_recorded=1 mission_id=$missionId"
                exit 0
            }
        }
    }
    Start-Sleep -Seconds $PollIntervalSec
}

Write-Bad "Timeout after ${PollTimeoutSec}s - no receipt_recorded with summary for mission $missionId ."
Write-Info "Diagnose: (1) Coordinator running with REDIS_URL, CONTROL_PLANE_URL, DASHCLAW_BASE_URL, DASHCLAW_API_KEY? (2) Executor running with CONTROL_PLANE_API_KEY? (3) DashClaw /api/guard returned allow (not deny)? (4) openclaw agent works? (5) Mission status: try GET $script:Base/api/v1/missions/$missionId"
exit 1
