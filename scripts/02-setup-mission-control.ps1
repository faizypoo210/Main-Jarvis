<#
.SYNOPSIS
  Phase 2: Clone Mission Control, write JARVIS env files, apply host-DB compose, build and start stack.
#>
$ErrorActionPreference = "Stop"

$JarvisRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = "C:\projects\openclaw-mission-control"
$RepoUrl = "https://github.com/abhi1693/openclaw-mission-control"
$ComposeTemplateYml = Join-Path $JarvisRoot "config\mission-control-compose.yml"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Step "=== JARVIS Phase 2: Mission Control ==="

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Fail "git not found. Install Git for Windows."
    exit 1
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fail "docker not found. Complete Phase 1 first."
    exit 1
}

$projects = "C:\projects"
if (-not (Test-Path -LiteralPath $projects)) {
    New-Item -ItemType Directory -Path $projects -Force | Out-Null
}

if (-not (Test-Path -LiteralPath "$RepoRoot\.git")) {
    Write-Step "Cloning Mission Control..."
    git clone $RepoUrl $RepoRoot
    if ($LASTEXITCODE -ne 0) { Write-Fail "git clone failed"; exit 1 }
    Write-Ok "Repository cloned"
} else {
    Write-Ok "Repository already present: $RepoRoot"
}

if (-not (Test-Path -LiteralPath $ComposeTemplateYml)) {
    Write-Fail "Missing compose template: $ComposeTemplateYml"
    exit 1
}

Copy-Item -LiteralPath $ComposeTemplateYml -Destination (Join-Path $RepoRoot "compose.yml") -Force
Write-Ok "Applied JARVIS compose.yml (host PostgreSQL + Redis)"

$localToken = "+ktPQuNTGmw072CnNMgRd7t3cVFzWMp6dmSh7Hw+SjPmZ69iu9ogebldNCJ/1zbN"

$rootEnv = @"
FRONTEND_PORT=3000
BACKEND_PORT=3001
AUTH_MODE=local
LOCAL_AUTH_TOKEN=$localToken
CORS_ORIGINS=http://localhost:3000
BASE_URL=http://localhost:3001
DB_AUTO_MIGRATE=true
NEXT_PUBLIC_API_URL=auto
"@

$backendEnv = @"
ENVIRONMENT=production
LOG_LEVEL=INFO
LOG_FORMAT=text
LOG_USE_UTC=false
REQUEST_LOG_SLOW_MS=1000
REQUEST_LOG_INCLUDE_HEALTH=false
DATABASE_URL=postgresql+psycopg://jarvis:jarvis_secure_password_2026@host.docker.internal:5432/jarvis_missions
CORS_ORIGINS=http://localhost:3000
BASE_URL=http://localhost:3001
AUTH_MODE=local
LOCAL_AUTH_TOKEN=$localToken
DB_AUTO_MIGRATE=true
RQ_REDIS_URL=redis://host.docker.internal:6379/0
RQ_QUEUE_NAME=default
RQ_DISPATCH_THROTTLE_SECONDS=2.0
RQ_DISPATCH_MAX_RETRIES=3
GATEWAY_MIN_VERSION=2026.02.9
"@

Set-Content -LiteralPath (Join-Path $RepoRoot ".env") -Value $rootEnv -Encoding utf8
Set-Content -LiteralPath (Join-Path $RepoRoot "backend\.env") -Value $backendEnv -Encoding utf8
Write-Ok "Wrote root .env and backend\.env"

Push-Location $RepoRoot
try {
    Write-Step "docker compose build (this may take several minutes)..."
    docker compose -f compose.yml --env-file .env build
    if ($LASTEXITCODE -ne 0) { Write-Fail "docker compose build failed"; exit 1 }
    Write-Ok "docker compose build finished"

    Write-Step "docker compose up -d..."
    docker compose -f compose.yml --env-file .env up -d
    if ($LASTEXITCODE -ne 0) { Write-Fail "docker compose up failed"; exit 1 }
    Write-Ok "docker compose up -d finished"

    Write-Step "Waiting for backend /health..."
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:3001/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 3
    }
    if (-not $ready) {
        Write-Fail "Backend did not become healthy on http://localhost:3001/health"
        docker compose -f compose.yml --env-file .env ps
        docker compose -f compose.yml --env-file .env logs --tail=80 backend
        exit 1
    }
    Write-Ok "Backend health check passed"
} finally {
    Pop-Location
}

Write-Step "Opening Mission Control in default browser..."
Start-Process "http://localhost:3000"

Write-Host ""
Write-Ok "Phase 2 setup finished. Run .\scripts\02-verify-mission-control.ps1"
exit 0
