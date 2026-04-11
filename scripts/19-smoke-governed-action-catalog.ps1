#Requires -Version 5.1
<#
.SYNOPSIS
  Read-only smoke: GET /api/v1/operator/action-catalog + expected six governed actions.

.DESCRIPTION
  Does not mutate state. Exits 0 when catalog responds and all expected approval_action_type
  values are present. Skips nothing (failure = control plane down or contract drift).

  Emits: DAYWRAP governed_catalog <pass_count> <total_checks>
#>
$ErrorActionPreference = 'Continue'

function Get-CpBase {
    $u = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_URL', 'User')
    if ([string]::IsNullOrWhiteSpace($u)) { $u = $env:CONTROL_PLANE_URL }
    if ([string]::IsNullOrWhiteSpace($u)) { $u = 'http://127.0.0.1:8001' }
    return $u.TrimEnd('/')
}

$Expected = @(
    'github_create_issue'
    'github_create_pull_request'
    'github_merge_pull_request'
    'gmail_create_draft'
    'gmail_create_reply_draft'
    'gmail_send_draft'
)

$Base = Get-CpBase
$Uri = "$Base/api/v1/operator/action-catalog"

Write-Host "=== 19-smoke-governed-action-catalog (read-only) ===" -ForegroundColor Cyan
Write-Host "GET $Uri" -ForegroundColor DarkGray

$pass = 0
$fail = 0

try {
    $r = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 25
} catch {
    Write-Host "[FAIL] action-catalog — $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "DAYWRAP governed_catalog 0 1"
    exit 1
}

if ($null -eq $r -or $null -eq $r.actions) {
    Write-Host "[FAIL] action-catalog — missing actions array" -ForegroundColor Red
    Write-Host "DAYWRAP governed_catalog 0 1"
    exit 1
}

Write-Host "[PASS] GET /api/v1/operator/action-catalog (catalog_version=$($r.catalog_version))" -ForegroundColor Green
$pass++

$types = @{}
foreach ($a in @($r.actions)) {
    if ($a.approval_action_type) {
        $types[$a.approval_action_type] = $true
    }
}

foreach ($name in $Expected) {
    if ($types.ContainsKey($name)) {
        Write-Host "[PASS] catalog contains approval_action_type=$name" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "[FAIL] missing approval_action_type=$name" -ForegroundColor Red
        $fail++
    }
}

$total = $pass + $fail
Write-Host ""
Write-Host "DAYWRAP governed_catalog $pass $total"
if ($fail -gt 0) { exit 1 }
exit 0
