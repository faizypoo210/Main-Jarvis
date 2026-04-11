#Requires -Version 5.1
param(
    [switch]$ApprovalPath,
    [int]$TimeoutSec = 90,
    [int]$PollIntervalSec = 2,
    [string]$ControlPlaneUrl = $(if ($env:JARVIS_CONTROL_PLANE_URL) { $env:JARVIS_CONTROL_PLANE_URL } else { 'http://localhost:8001' }),
    [string]$ApiKey = $(if ($env:CONTROL_PLANE_API_KEY) { $env:CONTROL_PLANE_API_KEY } elseif ($env:JARVIS_CONTROL_PLANE_API_KEY) { $env:JARVIS_CONTROL_PLANE_API_KEY } else { '' }),
    [string]$HappyPathCommand = $(if ($env:JARVIS_SMOKE_COMMAND_TEXT) { $env:JARVIS_SMOKE_COMMAND_TEXT } else { 'Jarvis smoke test: reply with a short one-sentence system status confirmation.' }),
    [string]$ApprovalCommand = $(if ($env:JARVIS_SMOKE_APPROVAL_COMMAND_TEXT) { $env:JARVIS_SMOKE_APPROVAL_COMMAND_TEXT } else { 'Jarvis smoke test: send an email to test@example.com saying the system is online.' })
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Write-Info([string]$Message) {
    Write-Host $Message -ForegroundColor Gray
}

function Fail([string]$Message, [int]$Code = 1) {
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    exit $Code
}

function Get-Json([string]$Url, [hashtable]$Headers) {
    return Invoke-RestMethod -Uri $Url -Headers $Headers -Method Get -TimeoutSec 15
}

function Post-Json([string]$Url, [hashtable]$Headers, [object]$Body) {
    $json = $Body | ConvertTo-Json -Depth 10 -Compress
    return Invoke-RestMethod -Uri $Url -Headers $Headers -Method Post -Body $json -ContentType 'application/json; charset=utf-8' -TimeoutSec 20
}

function Test-DockerExec([string]$Container, [string[]]$Command) {
    $out = & docker exec $Container @Command 2>&1 | Out-String
    return @{ Ok = ($LASTEXITCODE -eq 0); Output = $out.Trim() }
}

$headers = @{ Accept = 'application/json' }
if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
    $headers['x-api-key'] = $ApiKey
}

Write-Step 'Preflight'

try {
    $health = Invoke-WebRequest -Uri "$ControlPlaneUrl/health" -UseBasicParsing -TimeoutSec 10
    if ($health.StatusCode -ne 200) {
        Fail "Control Plane health probe returned HTTP $($health.StatusCode)."
    }
    Write-Host '[PASS] Control Plane /health' -ForegroundColor Green
} catch {
    Fail "Control Plane health probe failed on $ControlPlaneUrl/health — $($_.Exception.Message)"
}

$pg = Test-DockerExec 'jarvis-postgres' @('pg_isready', '-d', 'jarvis_missions', '-U', 'jarvis')
if (-not $pg.Ok) { Fail "Postgres check failed: $($pg.Output)" }
Write-Host '[PASS] PostgreSQL ready (jarvis-postgres)' -ForegroundColor Green

$redis = Test-DockerExec 'jarvis-redis' @('redis-cli', 'PING')
if (-not $redis.Ok -or $redis.Output -notmatch 'PONG') { Fail "Redis check failed: $($redis.Output)" }
Write-Host '[PASS] Redis PING (jarvis-redis)' -ForegroundColor Green

try {
    $ollama = Invoke-WebRequest -Uri 'http://localhost:11434' -UseBasicParsing -TimeoutSec 5
    if ($ollama.StatusCode -eq 200) {
        Write-Host '[PASS] Ollama reachable (11434)' -ForegroundColor Green
    } else {
        Write-Host "[WARN] Ollama probe returned HTTP $($ollama.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host '[WARN] Ollama not reachable on 11434 — continuing because executor may still be wired differently.' -ForegroundColor Yellow
}

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
    Fail 'openclaw command not found on PATH.'
}
$out = & openclaw status 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Fail "openclaw status failed: $($out.Trim())"
}
Write-Host '[PASS] openclaw status' -ForegroundColor Green

if ($env:DASHCLAW_BASE_URL) {
    try {
        $dash = Invoke-WebRequest -Uri $env:DASHCLAW_BASE_URL -UseBasicParsing -TimeoutSec 10
        Write-Host "[PASS] DashClaw probe $($env:DASHCLAW_BASE_URL)" -ForegroundColor Green
    } catch {
        Write-Host "[WARN] DashClaw probe failed at $($env:DASHCLAW_BASE_URL) — coordinator may still be the failing link." -ForegroundColor Yellow
    }
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Host '[WARN] CONTROL_PLANE_API_KEY / JARVIS_CONTROL_PLANE_API_KEY not set. POST /api/v1/commands may fail with 401.' -ForegroundColor Yellow
}

$commandText = if ($ApprovalPath) { $ApprovalCommand } else { $HappyPathCommand }
$modeName = if ($ApprovalPath) { 'approval-path' } else { 'happy-path' }
Write-Step "Submit command ($modeName)"
Write-Info "Command: $commandText"

try {
    $response = Post-Json "$ControlPlaneUrl/api/v1/commands" $headers @{ text = $commandText; source = 'api' }
} catch {
    Fail "POST /api/v1/commands failed — $($_.Exception.Message)"
}

$missionId = [string]$response.mission_id
if ([string]::IsNullOrWhiteSpace($missionId)) {
    Fail 'Command intake response did not include mission_id.'
}
Write-Host "[PASS] Mission created: $missionId" -ForegroundColor Green

Write-Step 'Polling mission state'
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$approvalSeen = $false
$lastStatus = ''
$lastEventTypes = @()

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $PollIntervalSec

    try {
        $mission = Get-Json "$ControlPlaneUrl/api/v1/missions/$missionId" $headers
        $events = @(Get-Json "$ControlPlaneUrl/api/v1/missions/$missionId/events" $headers)
        $approvals = @()
        try {
            $approvals = @(Get-Json "$ControlPlaneUrl/api/v1/approvals/pending" $headers)
        } catch {
            Write-Host '[WARN] Could not fetch pending approvals during poll.' -ForegroundColor Yellow
        }

        $lastStatus = [string]$mission.status
        $lastEventTypes = @($events | ForEach-Object { [string]$_.event_type })

        $receiptEvent = $null
        foreach ($event in $events) {
            if ($event.event_type -eq 'receipt_recorded' -and $event.payload -and $event.payload.summary) {
                $summaryText = [string]$event.payload.summary
                if (-not [string]::IsNullOrWhiteSpace($summaryText)) {
                    $receiptEvent = $event
                }
            }
        }

        $pendingApproval = $approvals | Where-Object { [string]$_.mission_id -eq $missionId -and [string]$_.status -eq 'pending' } | Select-Object -First 1
        if ($pendingApproval) {
            $approvalSeen = $true
        }

        if ($ApprovalPath) {
            if ($receiptEvent) {
                Fail 'Approval-path smoke test reached receipt_recorded before creating a pending approval. Guard likely allowed execution.'
            }
            if ($pendingApproval) {
                Write-Host "SMOKE_APPROVAL_PASS pending_approval=1 mission_id=$missionId approval_id=$($pendingApproval.id)" -ForegroundColor Green
                exit 0
            }
        } else {
            if ($receiptEvent) {
                $summaryText = [string]$receiptEvent.payload.summary
                Write-Host "SMOKE_E2E_PASS receipt_recorded=1 mission_id=$missionId" -ForegroundColor Green
                Write-Host "Summary: $summaryText" -ForegroundColor Green
                exit 0
            }
        }
    } catch {
        Write-Host "[WARN] Poll tick failed — $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Step 'Diagnostics'
Write-Info "mission_id: $missionId"
Write-Info "last mission status: $lastStatus"
Write-Info "last events: $($lastEventTypes -join ', ')"

if ($ApprovalPath) {
    if ($lastStatus -eq 'awaiting_approval' -or $approvalSeen) {
        Fail 'Approval-path smoke test timed out even though mission appears to be awaiting approval. Check /api/v1/approvals/pending visibility and API key wiring.'
    }
    if ($lastStatus -eq 'failed') {
        Fail 'Approval-path smoke test failed before a pending approval record was observed. Check coordinator / DashClaw behavior.'
    }
    Fail 'Approval-path smoke test timed out without a pending approval. Check coordinator, DashClaw, and the approval-triggering command text.'
}

switch ($lastStatus) {
    'pending' {
        Fail 'Mission never left pending. Check control plane -> Redis -> coordinator wiring.'
    }
    'active' {
        Fail 'Mission became active but no receipt_recorded summary appeared. Check executor, openclaw agent execution, and receipt posting.'
    }
    'awaiting_approval' {
        Fail 'Mission is awaiting approval on the happy path. DashClaw likely classified the smoke command as risky; override JARVIS_SMOKE_COMMAND_TEXT with a safer read-only command.'
    }
    'failed' {
        Fail 'Mission failed before a successful receipt_recorded summary. Check executor logs, OpenClaw health, and receipt writes.'
    }
    default {
        Fail 'Smoke test timed out without a terminal signal. Check control plane, coordinator, executor, and OpenClaw logs.'
    }
}
