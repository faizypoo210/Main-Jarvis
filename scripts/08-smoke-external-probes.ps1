#Requires -Version 5.1
# Honest external provider probes: GitHub /user, Gmail profile. No mutations.
# Exit 1 only when a probe runs and fails. Skips when tokens absent (exit 0).
$ErrorActionPreference = 'Continue'

$probePass = 0
$probeTotal = 0

function Invoke-GitHubUserProbe {
    $t = $env:JARVIS_GITHUB_TOKEN
    if ([string]::IsNullOrWhiteSpace($t)) {
        Write-Host "[SKIP] GitHub user probe - JARVIS_GITHUB_TOKEN not set (skipped_missing_auth)" -ForegroundColor Yellow
        Write-Host "SMOKE_EXT github skipped_missing_auth"
        return
    }
    $script:probeTotal++
    try {
        $headers = @{
            Authorization = "Bearer $t"
            Accept        = 'application/vnd.github+json'
            'User-Agent'  = 'Jarvis-Smoke-Probe'
        }
        $r = Invoke-RestMethod -Uri 'https://api.github.com/user' -Headers $headers -Method Get -TimeoutSec 20
        if ($r.login) {
            Write-Host "[PASS] GitHub token accepted (login=$($r.login))" -ForegroundColor Green
            Write-Host "SMOKE_EXT github pass"
            $script:probePass++
        } else {
            Write-Host "[FAIL] GitHub /user - unexpected body" -ForegroundColor Red
            Write-Host "SMOKE_EXT github fail"
        }
    } catch {
        Write-Host "[FAIL] GitHub /user - $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "SMOKE_EXT github fail"
    }
}

function Invoke-GmailProfileProbe {
    $t = $env:JARVIS_GMAIL_ACCESS_TOKEN
    if ([string]::IsNullOrWhiteSpace($t)) {
        Write-Host "[SKIP] Gmail profile - JARVIS_GMAIL_ACCESS_TOKEN not set (skipped_not_configured)" -ForegroundColor Yellow
        Write-Host "SMOKE_EXT gmail skipped_not_configured"
        return
    }
    $script:probeTotal++
    try {
        $headers = @{ Authorization = "Bearer $t" }
        $r = Invoke-RestMethod -Uri 'https://gmail.googleapis.com/gmail/v1/users/me/profile' -Headers $headers -Method Get -TimeoutSec 20
        if ($r.emailAddress) {
            Write-Host "[PASS] Gmail token accepted (email=$($r.emailAddress))" -ForegroundColor Green
            Write-Host "SMOKE_EXT gmail pass"
            $script:probePass++
        } else {
            Write-Host "[FAIL] Gmail profile - unexpected body" -ForegroundColor Red
            Write-Host "SMOKE_EXT gmail fail"
        }
    } catch {
        Write-Host "[FAIL] Gmail profile - $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "SMOKE_EXT gmail fail"
    }
}

Write-Host "=== 08-smoke-external-probes (read-only, optional) ===" -ForegroundColor Cyan

Invoke-GitHubUserProbe
Invoke-GmailProfileProbe

if ($probeTotal -eq 0) {
    Write-Host "PHASE8 external_probes skipped 0 0"
    exit 0
}
Write-Host "PHASE8 external_probes $probePass $probeTotal"
if ($probePass -lt $probeTotal) { exit 1 }
exit 0
