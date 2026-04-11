#Requires -Version 5.1
<#
.SYNOPSIS
  Read-only control-plane checks for operator APIs + updates (governed stack truth surface).

.DESCRIPTION
  Does not mutate missions. Exits 0 only if all executed checks pass (skipped checks do not fail).
  PHASE8 operator_apis <pass_count> <total_executed>

  SSE stream requires CONTROL_PLANE_API_KEY (same as server). If unset, SSE is skipped (not a failure).
#>
$ErrorActionPreference = 'Continue'

function Get-CpBase {
    $u = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_URL', 'User')
    if ([string]::IsNullOrWhiteSpace($u)) { $u = $env:CONTROL_PLANE_URL }
    if ([string]::IsNullOrWhiteSpace($u)) { $u = 'http://127.0.0.1:8001' }
    return $u.TrimEnd('/')
}

function Get-ApiKey {
    $k = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_API_KEY', 'User')
    if ([string]::IsNullOrWhiteSpace($k)) { $k = $env:CONTROL_PLANE_API_KEY }
    if ([string]::IsNullOrWhiteSpace($k)) { $k = $env:JARVIS_SMOKE_API_KEY }
    return $k
}

function Test-JsonGet {
    param([string]$Uri, [string]$Name)
    try {
        $r = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 25
        if ($null -eq $r) {
            Write-Host "[FAIL] $Name (empty body)" -ForegroundColor Red
            return $false
        }
        Write-Host "[PASS] $Name" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[FAIL] $Name - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

$Base = Get-CpBase
$Api = "$Base/api/v1"
$Key = Get-ApiKey

Write-Host "=== 08-smoke-operator-control-plane (read-only) ===" -ForegroundColor Cyan
Write-Host "Base: $Base" -ForegroundColor DarkGray

$pass = 0
$fail = 0

function Add-Result {
    param([bool]$Ok)
    if ($Ok) { $script:pass++ } else { $script:fail++ }
}

$checks = @(
    @{ Uri = "$Api/system/health"; Name = 'GET /api/v1/system/health' }
    @{ Uri = "$Api/operator/integrations"; Name = 'GET /api/v1/operator/integrations' }
    @{ Uri = "$Api/operator/activity?limit=1"; Name = 'GET /api/v1/operator/activity?limit=1' }
    @{ Uri = "$Api/operator/usage"; Name = 'GET /api/v1/operator/usage' }
    @{ Uri = "$Api/operator/memory/counts"; Name = 'GET /api/v1/operator/memory/counts' }
    @{ Uri = "$Api/operator/heartbeat"; Name = 'GET /api/v1/operator/heartbeat' }
    @{ Uri = "$Api/operator/evals?window_hours=24"; Name = 'GET /api/v1/operator/evals?window_hours=24' }
    @{ Uri = "$Api/updates"; Name = 'GET /api/v1/updates (SSE hub status)' }
)

foreach ($c in $checks) {
    Add-Result (Test-JsonGet -Uri $c.Uri -Name $c.Name)
}

# Pending list + optional bundle
$pending = $null
try {
    $pending = Invoke-RestMethod -Uri "$Api/approvals/pending" -Method Get -TimeoutSec 25
    Write-Host "[PASS] GET /api/v1/approvals/pending" -ForegroundColor Green
    Add-Result $true
} catch {
    Write-Host "[FAIL] GET /api/v1/approvals/pending - $($_.Exception.Message)" -ForegroundColor Red
    Add-Result $false
}

$rows = @()
if ($null -ne $pending) { $rows = @($pending) }

if ($rows.Count -ge 1) {
    $aid = $rows[0].id.ToString()
    $bUri = "$Api/approvals/$aid/bundle"
    try {
        $bd = Invoke-RestMethod -Uri $bUri -Method Get -TimeoutSec 25
        if ($bd.packet -and $bd.packet.kind) {
            Write-Host "[PASS] GET /api/v1/approvals/{id}/bundle (id=$aid kind=$($bd.packet.kind))" -ForegroundColor Green
            Add-Result $true
        } else {
            Write-Host "[FAIL] GET approval bundle — missing packet.kind" -ForegroundColor Red
            Add-Result $false
        }
    } catch {
        Write-Host "[FAIL] GET /api/v1/approvals/{id}/bundle - $($_.Exception.Message)" -ForegroundColor Red
        Add-Result $false
    }
} else {
    Write-Host "[SKIP] GET /api/v1/approvals/{id}/bundle — no pending approvals" -ForegroundColor Yellow
}

# SSE (optional)
$sseLabel = 'GET /api/v1/updates/stream (SSE, x-api-key)'
if ([string]::IsNullOrWhiteSpace($Key)) {
    Write-Host "[SKIP] $sseLabel — CONTROL_PLANE_API_KEY not set" -ForegroundColor Yellow
    Write-Host "SMOKE_OPERATOR_SSE skip no_api_key"
} else {
    try {
        $req = [System.Net.HttpWebRequest]::Create("$Api/updates/stream")
        $req.Method = 'GET'
        $req.Headers['x-api-key'] = $Key
        $req.Accept = 'text/event-stream'
        $req.Timeout = 4000
        $resp = $req.GetResponse()
        $stream = $resp.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $null = $reader.ReadLine()
        $reader.Close()
        $resp.Close()
        Write-Host "[PASS] $sseLabel" -ForegroundColor Green
        Add-Result $true
        Write-Host "SMOKE_OPERATOR_SSE pass"
    } catch {
        Write-Host "[FAIL] $sseLabel - $($_.Exception.Message)" -ForegroundColor Red
        Add-Result $false
        Write-Host "SMOKE_OPERATOR_SSE fail"
    }
}

$total = $pass + $fail
Write-Host ""
Write-Host "Summary: $pass/$total checks passed." -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Yellow' })
Write-Host "PHASE8 operator_apis $pass $total"
if ($fail -gt 0) { exit 1 }
exit 0
