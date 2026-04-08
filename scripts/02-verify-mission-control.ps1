<#
.SYNOPSIS
  Phase 2: Verify Mission Control containers and HTTP endpoints.
  Note: upstream API health is at /health (not /api/health).
#>
$ErrorActionPreference = "Stop"

$RepoRoot = "C:\projects\openclaw-mission-control"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Step "=== JARVIS Phase 2: Verify Mission Control ==="

if (-not (Test-Path -LiteralPath $RepoRoot)) {
    Write-Fail "Mission Control repo not found at $RepoRoot"
    exit 1
}

Push-Location $RepoRoot
try {
    Write-Step "--- docker compose ps ---"
    docker compose -f compose.yml --env-file .env ps
    if ($LASTEXITCODE -ne 0) { Write-Fail "docker compose ps failed"; exit 1 }

    Write-Step "--- Backend /health (port 3001) ---"
    try {
        $h = Invoke-WebRequest -Uri "http://localhost:3001/health" -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
        if ($h.StatusCode -eq 200) {
            Write-Ok "GET http://localhost:3001/health -> $($h.StatusCode)"
            Write-Host $h.Content
        } else {
            Write-Fail "Unexpected status: $($h.StatusCode)"
            exit 1
        }
    } catch {
        Write-Fail "Backend health request failed: $_"
        docker compose -f compose.yml --env-file .env logs --tail=100 backend
        exit 1
    }

    Write-Step "--- Frontend (port 3000) ---"
    try {
        $f = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
        Write-Ok "GET http://localhost:3000 -> $($f.StatusCode)"
    } catch {
        Write-Fail "Frontend check failed: $_"
        docker compose -f compose.yml --env-file .env logs --tail=80 frontend
        exit 1
    }

    Write-Step "--- Recent backend logs ---"
    docker compose -f compose.yml --env-file .env logs --tail=30 backend
} finally {
    Pop-Location
}

Write-Host ""
Write-Ok "Phase 2 verification complete."
exit 0
