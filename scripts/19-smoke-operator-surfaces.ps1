#Requires -Version 5.1
<#
.SYNOPSIS
  Read-only GETs for operator inbox, workers, cost guardrails, and cost events.

.DESCRIPTION
  Complements 08-smoke-operator-control-plane.ps1 (which covers approvals bundle, heartbeat, etc.).
  Emits: DAYWRAP operator_surfaces <pass> <total>
#>
$ErrorActionPreference = 'Continue'

function Get-CpBase {
    $u = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_URL', 'User')
    if ([string]::IsNullOrWhiteSpace($u)) { $u = $env:CONTROL_PLANE_URL }
    if ([string]::IsNullOrWhiteSpace($u)) { $u = 'http://127.0.0.1:8001' }
    return $u.TrimEnd('/')
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
        Write-Host "[FAIL] $Name — $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

$Base = Get-CpBase
$Api = "$Base/api/v1"

Write-Host "=== 19-smoke-operator-surfaces (read-only) ===" -ForegroundColor Cyan
Write-Host "Base: $Base" -ForegroundColor DarkGray

$pass = 0
$fail = 0

function Add-Result { param([bool]$Ok) if ($Ok) { $script:pass++ } else { $script:fail++ } }

$checks = @(
    @{ Uri = "$Api/operator/inbox?limit=5"; Name = 'GET /api/v1/operator/inbox?limit=5' }
    @{ Uri = "$Api/operator/heartbeat"; Name = 'GET /api/v1/operator/heartbeat' }
    @{ Uri = "$Api/operator/workers"; Name = 'GET /api/v1/operator/workers' }
    @{ Uri = "$Api/operator/cost-guardrails"; Name = 'GET /api/v1/operator/cost-guardrails' }
    @{ Uri = "$Api/operator/cost-events?limit=5"; Name = 'GET /api/v1/operator/cost-events?limit=5' }
)

foreach ($c in $checks) {
    Add-Result (Test-JsonGet -Uri $c.Uri -Name $c.Name)
}

$total = $pass + $fail
Write-Host ""
Write-Host "DAYWRAP operator_surfaces $pass $total"
if ($fail -gt 0) { exit 1 }
exit 0
