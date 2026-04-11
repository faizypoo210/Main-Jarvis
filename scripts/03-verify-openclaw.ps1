<#
.SYNOPSIS
  Verifies gateway port, openclaw status, gateway health (WS + token), optional agent chat, and GET http://localhost:18789/ (never uses openclaw doctor).
  Optional agent test: set User env JARVIS_RUN_AGENT_VERIFY=1 (uses whatever model/credentials are configured in OpenClaw).
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
if ([string]::IsNullOrWhiteSpace($gwTok) -or ($gwTok -match '^(<|PLACEHOLDER|REPLACE)')) {
    Write-Fail "Gateway token missing or still a placeholder in $cfgPath. Set JARVIS_OPENCLAW_GATEWAY_TOKEN and run scripts/03-configure-openclaw.ps1 (see docs/SECRET_ROTATION.md)."
    exit 1
}

Write-Step "--- openclaw gateway health (RPC) ---"
openclaw gateway health --url "ws://127.0.0.1:18789" --token $gwTok
if ($LASTEXITCODE -ne 0) {
    Write-Fail "openclaw gateway health failed"
    exit 1
}
Write-Ok "gateway health OK"

Write-Step "--- Test message to main agent (optional) ---"
$runAgent = [Environment]::GetEnvironmentVariable("JARVIS_RUN_AGENT_VERIFY", "User")
if ([string]::IsNullOrWhiteSpace($runAgent)) { $runAgent = $env:JARVIS_RUN_AGENT_VERIFY }
if ($runAgent -ne "1") {
    Write-Warn "Skipping agent chat (set User env JARVIS_RUN_AGENT_VERIFY=1 to enable; requires working provider credentials in auth-profiles / env per OpenClaw)."
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

Write-Step "--- Related services (localhost) ---"
Write-Host "Control Plane: http://localhost:8001  |  Command Center: http://localhost:5173  |  Gateway: http://localhost:18789" -ForegroundColor DarkGray
Write-Ok "Phase 3 verification complete."
exit 0
