#Requires -Version 5.1
<#
.SYNOPSIS
  Smoke test: (1) local Ollama lane via /api/generate, (2) OpenClaw execution lane via control plane -> executor receipt with execution_meta.

  Requires: stack running, CONTROL_PLANE_API_KEY, DashClaw allowing the test command (same constraints as 09-smoke-test-e2e.ps1).
#>
$ErrorActionPreference = 'Stop'

$OLLAMA_MODEL = $env:OLLAMA_MODEL
if ([string]::IsNullOrWhiteSpace($OLLAMA_MODEL)) { $OLLAMA_MODEL = 'qwen3:4b' }

function Get-ApiKey {
    $k = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_API_KEY', 'User')
    if ([string]::IsNullOrWhiteSpace($k)) { $k = $env:CONTROL_PLANE_API_KEY }
    return $k
}

Write-Host "=== 11-smoke-model-lanes ===" -ForegroundColor Cyan

# --- Lane 1: local Ollama (direct; voice stack uses same model) ---
Write-Host "--- Local lane (Ollama generate) ---" -ForegroundColor Cyan
try {
    $body = @{
        model  = $OLLAMA_MODEL
        prompt = 'Say exactly: LOCAL_LANE_OK'
        stream = $false
    } | ConvertTo-Json -Compress
    $gen = Invoke-RestMethod -Uri 'http://localhost:11434/api/generate' -Method Post -Body $body -ContentType 'application/json; charset=utf-8' -TimeoutSec 120
    $resp = ($gen.response | Out-String).Trim()
    if ($resp -match 'LOCAL_LANE_OK' -or $resp.Length -gt 0) {
        Write-Host "[PASS] Local lane: Ollama /api/generate ($OLLAMA_MODEL)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Ollama returned empty response" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[FAIL] Local lane: $_" -ForegroundColor Red
    exit 1
}

# --- Lane 2: Mission path + OpenClaw execution (routing_decided + executor receipt) ---
Write-Host "--- Mission + execution lane (control plane -> coordinator -> executor -> OpenClaw) ---" -ForegroundColor Cyan
$apiKey = Get-ApiKey
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host "[FAIL] CONTROL_PLANE_API_KEY not set (required for command POST)." -ForegroundColor Red
    exit 1
}

$headers = @{
    'x-api-key'    = $apiKey
    'Content-Type' = 'application/json; charset=utf-8'
}
$cmd = 'Model lane smoke: reply with exactly: EXEC_LANE_OK'
$body2 = @{ text = $cmd; source = 'api' } | ConvertTo-Json -Compress

try {
    $cmdResp = Invoke-RestMethod -Uri 'http://localhost:8001/api/v1/commands' -Method Post -Headers $headers -Body $body2 -TimeoutSec 60
} catch {
    Write-Host "[FAIL] POST /api/v1/commands: $_" -ForegroundColor Red
    exit 1
}
$missionId = $cmdResp.mission_id
Write-Host "[INFO] mission_id=$missionId" -ForegroundColor DarkGray

$deadline = (Get-Date).AddSeconds(240)
$okExec = $false
$sawRouting = $false
while ((Get-Date) -lt $deadline) {
    try {
        $ms = Invoke-RestMethod -Uri "http://localhost:8001/api/v1/missions/$missionId" -Method Get -TimeoutSec 15
        if ($ms.status -eq 'awaiting_approval') {
            Write-Host "[FAIL] Mission awaiting_approval (DashClaw blocked execution). Use a command allowed by guard or adjust policy." -ForegroundColor Red
            exit 1
        }
    } catch { }
    try {
        $events = Invoke-RestMethod -Uri "http://localhost:8001/api/v1/missions/$missionId/events" -Method Get -TimeoutSec 30
    } catch {
        Write-Host "[FAIL] GET events: $_" -ForegroundColor Red
        exit 1
    }
    foreach ($e in @($events)) {
        if ($e.event_type -eq 'routing_decided' -and $e.payload) {
            $rp = $e.payload
            $req = [string]$rp.requested_lane
            $act = [string]$rp.actual_lane
            if ($req -and $act) {
                Write-Host "[PASS] routing_decided: requested=$req actual=$act fallback=$($rp.fallback_applied)" -ForegroundColor Green
                $sawRouting = $true
            }
        }
        if ($e.event_type -eq 'receipt_recorded' -and $e.payload) {
            $p = $e.payload
            $em = $null
            if ($p.PSObject.Properties['execution_meta']) { $em = $p.execution_meta }
            if ($null -ne $em) {
                $lt = $null
                if ($em.PSObject.Properties['lane_truth']) { $lt = $em.lane_truth }
                $oml = [string]$em.openclaw_model_lane
                if (-not $oml) { $oml = [string]$em.lane }
                Write-Host "[PASS] Execution receipt: openclaw_model_lane=$oml gateway_model=$($em.gateway_model)" -ForegroundColor Green
                if ($null -ne $lt) {
                    Write-Host "[PASS] execution_meta.lane_truth present (schema=$($lt.schema_version))" -ForegroundColor Green
                } else {
                    Write-Host "[WARN] execution_meta.lane_truth missing (older executor?)" -ForegroundColor Yellow
                }
                $okExec = $true
            }
        }
    }
    if ($okExec) { break }
    Start-Sleep -Seconds 2
}

if (-not $okExec) {
    Write-Host "[FAIL] Timeout waiting for executor receipt with execution_meta (check coordinator, executor, DashClaw allow, gateway)." -ForegroundColor Red
    exit 1
}

if (-not $sawRouting) {
    Write-Host "[WARN] No routing_decided on timeline (unexpected if coordinator posted events)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "SMOKE_MODEL_LANES_PASS local=1 execution_path=1 routing_observed=$sawRouting" -ForegroundColor Green
exit 0
