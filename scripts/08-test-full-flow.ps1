#Requires -Version 5.1
# Phase 8: Two OpenClaw agent turns for end-to-end flow (read-only aside from agent execution).
$ErrorActionPreference = 'Continue'

$pass = 0
$fail = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Probe)
    try {
        $ok = & $Probe
        if ($ok) {
            Write-Host "[PASS] $Name"
            $script:pass++
        } else {
            Write-Host "[FAIL] $Name"
            $script:fail++
        }
    } catch {
        Write-Host "[FAIL] $Name - $($_.Exception.Message)"
        $script:fail++
    }
}

Write-Host "=== 08-test-full-flow ===" -ForegroundColor Cyan

$script:R1 = ''
$script:R2 = ''

Test-Step 'status report command completes' {
    $script:R1 = & openclaw agent --agent main --message 'Create a brief status report of the JARVIS system. List what you know about the current deployment.' --timeout 600 2>&1 | Out-String
    Write-Host "--- agent response (status report) ---"
    Write-Host $script:R1
    if ($LASTEXITCODE -ne 0) { return $false }
    if ($script:R1 -match '(?i)Config invalid|Failed to start CLI') { return $false }
    return ($script:R1.Trim().Length -gt 0)
}

Test-Step 'status report length > 50 characters' {
    if ($script:R1 -match '(?i)Config invalid|Failed to start CLI') { return $false }
    return ($script:R1.Trim().Length -gt 50)
}

Test-Step 'tools question command completes' {
    $script:R2 = & openclaw agent --agent main --message 'What tools and integrations do you have available?' --timeout 600 2>&1 | Out-String
    Write-Host "--- agent response (tools) ---"
    Write-Host $script:R2
    if ($LASTEXITCODE -ne 0) { return $false }
    if ($script:R2 -match '(?i)Config invalid|Failed to start CLI') { return $false }
    return ($script:R2.Trim().Length -gt 0)
}

Test-Step 'tools response mentions integration keyword' {
    if ($script:R2 -match '(?i)Config invalid|Failed to start CLI') { return $false }
    $t = $script:R2.ToLowerInvariant()
    return ($t -match 'gmail|composio|github|calendar|notion')
}

Write-Host ""
Write-Host "Summary: $pass/4 checks passed." -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Yellow' })
Write-Host "PHASE8 fullflow $pass 4"
if ($fail -gt 0) { exit 1 }
exit 0
