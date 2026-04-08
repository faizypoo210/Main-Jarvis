<#
.SYNOPSIS
  Phase 1: Ensure Docker Desktop is available, create data dirs, start PostgreSQL and Redis containers (idempotent).
#>
$ErrorActionPreference = "Stop"

# Docker writes expected errors to stderr; avoid terminating the script on inspect failures.
function Invoke-DockerIgnoreStderr {
    param(
        [Parameter(Mandatory = $false, ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & docker @Arguments 2>&1 | Out-Null
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
}

$PostgresName = "jarvis-postgres"
$RedisName = "jarvis-redis"
$DataPostgres = "C:\jarvis-data\postgres"
$DataRedis = "C:\jarvis-data\redis"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Step "=== JARVIS Phase 1: Docker + databases ==="

# --- Docker CLI present ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fail "Docker CLI not found. Install Docker Desktop for Windows, then enable WSL2 backend and start Docker Desktop."
    Write-Host "  1. Download: https://docs.docker.com/desktop/install/windows-install/"
    Write-Host "  2. After install, start Docker Desktop and wait until it shows 'Running'."
    Write-Host "  3. Re-run: .\scripts\01-install-docker-databases.ps1"
    exit 1
}
Write-Ok "Docker CLI found"

# --- Docker daemon ---
if ((Invoke-DockerIgnoreStderr info) -ne 0) {
    Write-Fail "Docker daemon not reachable. Start Docker Desktop and wait until it is fully running."
    exit 1
}
Write-Ok "Docker daemon is reachable"

# --- Data directories ---
foreach ($d in @($DataPostgres, $DataRedis)) {
    if (-not (Test-Path -LiteralPath $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Write-Ok "Created directory: $d"
    } else {
        Write-Ok "Directory exists: $d"
    }
}

function Ensure-Container {
    param(
        [string]$Name,
        [scriptblock]$CreateIfMissing
    )
    if ((Invoke-DockerIgnoreStderr container inspect $Name) -eq 0) {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $running = docker inspect -f '{{.State.Running}}' $Name 2>&1
        $ErrorActionPreference = $prev
        if ($running -eq "true") {
            Write-Ok "Container already running: $Name"
            return
        }
        Write-Step "Starting existing container: $Name"
        if ((Invoke-DockerIgnoreStderr start $Name) -ne 0) { throw "docker start $Name failed" }
        Write-Ok "Started: $Name"
        return
    }
    Write-Step "Creating container: $Name"
    $prevEa = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $CreateIfMissing 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Create failed for $Name (docker exit $LASTEXITCODE)" }
    } finally {
        $ErrorActionPreference = $prevEa
    }
    Write-Ok "Created and started: $Name"
}

# --- PostgreSQL ---
Ensure-Container -Name $PostgresName -CreateIfMissing {
    docker run -d `
        --name $PostgresName `
        --restart unless-stopped `
        -e POSTGRES_USER=jarvis `
        -e POSTGRES_PASSWORD=jarvis_secure_password_2026 `
        -e POSTGRES_DB=jarvis_missions `
        -p 5432:5432 `
        -v "${DataPostgres}:/var/lib/postgresql/data" `
        postgres:16
}

# --- Redis (AOF persistence) ---
Ensure-Container -Name $RedisName -CreateIfMissing {
    docker run -d `
        --name $RedisName `
        --restart unless-stopped `
        -p 6379:6379 `
        -v "${DataRedis}:/data" `
        redis:7-alpine `
        redis-server --appendonly yes
}

# --- Quick running check ---
$prevEa = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try {
    $pgRun = docker inspect -f '{{.State.Running}}' $PostgresName 2>&1
    $rdRun = docker inspect -f '{{.State.Running}}' $RedisName 2>&1
} finally {
    $ErrorActionPreference = $prevEa
}
if ("$pgRun" -ne "true" -or "$rdRun" -ne "true") {
    Write-Fail "Expected both containers running. Check: docker ps -a"
    exit 1
}

Write-Host ""
Write-Ok "PostgreSQL running on port 5432"
Write-Ok "Redis running on port 6379"
Write-Host ""
Write-Host "Phase 1 install script finished. Run .\scripts\01-verify-databases.ps1" -ForegroundColor Green

exit 0
