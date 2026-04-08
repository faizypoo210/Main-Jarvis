#Requires -Version 5.1
# Phase 8: Mission Control API checks (creates/deletes one test task; uses Bearer auth).
$ErrorActionPreference = 'Continue'

$BaseUrl = 'http://localhost:3001'
$Bearer = [Environment]::GetEnvironmentVariable('JARVIS_MISSION_CONTROL_TOKEN', 'User')
if ([string]::IsNullOrEmpty($Bearer)) {
    $Bearer = [Environment]::GetEnvironmentVariable('JARVIS_MISSION_CONTROL_TOKEN', 'Process')
}
if ([string]::IsNullOrEmpty($Bearer)) {
    $Bearer = '+ktPQuNTGmw072CnNMgRd7t3cVFzWMp6dmSh7Hw+SjPmZ69iu9ogebldNCJ/1zbN'
}

$headers = @{
    Authorization = "Bearer $Bearer"
}

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

Write-Host "=== 08-test-mission-control ===" -ForegroundColor Cyan

$script:TestBoardId = $null
$script:TestTaskId = $null

Test-Step 'GET /health 200' {
    $r = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 15
    return ($r.StatusCode -eq 200)
}

Test-Step 'POST create test mission task' {
    $boards = Invoke-RestMethod -Uri "$BaseUrl/api/v1/boards?limit=5&offset=0" -Headers $headers -Method Get -TimeoutSec 30
    if (-not $boards.items -or $boards.items.Count -eq 0) { return $false }
    $script:TestBoardId = $boards.items[0].id
    $body = @{ title = 'JARVIS E2E Test Mission'; status = 'inbox' } | ConvertTo-Json -Compress
    $created = Invoke-RestMethod -Uri "$BaseUrl/api/v1/boards/$($script:TestBoardId)/tasks" -Headers $headers -Method Post -Body $body -ContentType 'application/json; charset=utf-8' -TimeoutSec 60
    $script:TestTaskId = $created.id
    return ($null -ne $script:TestTaskId)
}

Test-Step 'GET tasks list contains test mission' {
    if (-not $script:TestBoardId) { return $false }
    $page = Invoke-RestMethod -Uri "$BaseUrl/api/v1/boards/$($script:TestBoardId)/tasks?limit=200&offset=0" -Headers $headers -Method Get -TimeoutSec 60
    $found = $false
    foreach ($t in $page.items) {
        if ($t.title -eq 'JARVIS E2E Test Mission') { $found = $true; break }
    }
    return $found
}

Test-Step 'DELETE test mission (cleanup)' {
    if (-not $script:TestBoardId -or -not $script:TestTaskId) { return $false }
    try {
        $del = Invoke-WebRequest -Uri "$BaseUrl/api/v1/boards/$($script:TestBoardId)/tasks/$($script:TestTaskId)" -Headers $headers -Method Delete -UseBasicParsing -TimeoutSec 60
        return ($del.StatusCode -ge 200 -and $del.StatusCode -lt 300)
    } catch {
        return $false
    }
}

Test-Step 'LAN Mission Control UI 10.0.0.249:3000' {
    $r = Invoke-WebRequest -Uri 'http://10.0.0.249:3000' -UseBasicParsing -TimeoutSec 20
    return ($r.StatusCode -eq 200)
}

Write-Host ""
Write-Host "Summary: $pass/5 checks passed." -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Yellow' })
Write-Host "PHASE8 missioncontrol $pass 5"
if ($fail -gt 0) { exit 1 }
exit 0
