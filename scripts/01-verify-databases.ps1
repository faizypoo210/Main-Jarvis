<#
.SYNOPSIS
  Verifies PostgreSQL and Redis containers and basic connectivity.
#>
$ErrorActionPreference = "Stop"

$PostgresName = "jarvis-postgres"
$RedisName = "jarvis-redis"

Write-Host "=== JARVIS Phase 1: Verify databases ===" -ForegroundColor Cyan
Write-Host ""

# Container status (single filter matches both names by prefix)
Write-Host "--- Docker containers ---" -ForegroundColor Cyan
docker ps -a --filter "name=jarvis-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

function Test-ContainerRunning([string]$Name) {
    $running = docker inspect -f '{{.State.Running}}' $Name 2>$null
    return $running -eq "true"
}

if (-not (Test-ContainerRunning $PostgresName)) {
    Write-Host "[FAIL] PostgreSQL container is not running" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] PostgreSQL container running" -ForegroundColor Green

if (-not (Test-ContainerRunning $RedisName)) {
    Write-Host "[FAIL] Redis container is not running" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Redis container running" -ForegroundColor Green

Write-Host ""
Write-Host "--- Connection tests ---" -ForegroundColor Cyan

# PostgreSQL: TCP inside container (-h 127.0.0.1); retry until server accepts connections
$pgOk = $false
$pgTest = ""
for ($i = 0; $i -lt 15; $i++) {
    $prevEa = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $pgTest = docker exec $PostgresName psql -h 127.0.0.1 -U jarvis -d jarvis_missions -tAc "SELECT 1" 2>&1
    } finally {
        $ErrorActionPreference = $prevEa
    }
    if ($LASTEXITCODE -eq 0 -and "$pgTest" -match "1") {
        $pgOk = $true
        break
    }
    Start-Sleep -Seconds 2
}
if ($pgOk) {
    Write-Host "[OK] Database connection successful (SELECT 1)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] PostgreSQL query failed after retries: $pgTest" -ForegroundColor Red
    exit 1
}

# Redis PING
$prevEa = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try {
    $redisPing = docker exec $RedisName redis-cli PING 2>&1
} finally {
    $ErrorActionPreference = $prevEa
}
if ("$redisPing" -match "PONG") {
    Write-Host "[OK] Redis PING successful" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Redis PING failed: $redisPing" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "--- Resource usage (docker stats snapshot, non-streaming) ---" -ForegroundColor Cyan
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $PostgresName $RedisName 2>$null

Write-Host ""
Write-Host "Expected:" -ForegroundColor Cyan
Write-Host "  [OK] PostgreSQL running on port 5432"
Write-Host "  [OK] Redis running on port 6379"
Write-Host "  [OK] Database connection successful"
Write-Host "  [OK] Redis PING successful"
Write-Host ""

exit 0
