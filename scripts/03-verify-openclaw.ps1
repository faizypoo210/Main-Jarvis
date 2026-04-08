<#
.SYNOPSIS
  Verifies gateway port, openclaw status, gateway health (WS + token), optional agent chat if ANTHROPIC_API_KEY is set, and GET http://localhost:18789/ (never uses openclaw doctor).
#>
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

Write-Step "=== JARVIS Phase 3: Verify OpenClaw Gateway ==="

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
    Write-Fail "openclaw not found."
    exit 1
}

$k = [Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
if (-not [string]::IsNullOrEmpty($k)) { $env:ANTHROPIC_API_KEY = $k }

Write-Step "--- Port 18789 listen check ---"
$prevEa = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try {
    $listen = @(Get-NetTCPConnection -LocalPort 18789 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" })
} finally {
    $ErrorActionPreference = $prevEa
}
if ($listen.Count -eq 0) {
    Write-Fail "Nothing listening on port 18789. Run .\scripts\03-start-gateway.ps1"
    exit 1
}
Write-Ok "Port 18789 is listening (PID(s): $($listen.OwningProcess -join ', '))"

Write-Step "--- openclaw status (not doctor) ---"
openclaw status
if ($LASTEXITCODE -ne 0) {
    Write-Fail "openclaw status exited $($LASTEXITCODE)"
    exit 1
}
Write-Ok "openclaw status completed"

$cfgPath = Join-Path $env:USERPROFILE ".openclaw\openclaw.json"
if (-not (Test-Path -LiteralPath $cfgPath)) {
    Write-Fail "Missing $cfgPath"
    exit 1
}
$cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json
$gwTok = $cfg.gateway.auth.token

Write-Step "--- openclaw gateway health (RPC) ---"
openclaw gateway health --url "ws://127.0.0.1:18789" --token $gwTok
if ($LASTEXITCODE -ne 0) {
    Write-Fail "openclaw gateway health failed"
    exit 1
}
Write-Ok "gateway health OK"

Write-Step "--- Test message to main agent ---"
if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User"))) {
    Write-Warn "Skipping agent chat: User ANTHROPIC_API_KEY is not set. Run .\scripts\03-configure-openclaw.ps1 (interactive), then restart the gateway (.\scripts\03-start-gateway.ps1), then re-run this script."
} else {
    $msg = "Jarvis, confirm you are online."
    openclaw agent --agent main -m $msg
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "openclaw agent test failed with exit $LASTEXITCODE"
        exit 1
    }
    Write-Ok "Agent test command finished"
}

Write-Step "--- HTTP GET http://localhost:18789/ ---"
try {
    $r = Invoke-WebRequest -Uri "http://localhost:18789/" -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
    Write-Ok "GET http://localhost:18789/ -> $($r.StatusCode) (len $($r.Content.Length))"
} catch {
    Write-Fail "GET http://localhost:18789/ failed: $_"
    exit 1
}

Write-Step "--- Mission Control vs gateway (localhost) ---"
Write-Host "Mission Control API: http://localhost:3001  |  Gateway: http://localhost:18789" -ForegroundColor DarkGray
Write-Ok "Phase 3 verification complete."
exit 0
