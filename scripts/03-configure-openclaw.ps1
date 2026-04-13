<#
.SYNOPSIS
  Writes %USERPROFILE%\.openclaw\openclaw.json and config.json (identical),
  with gateway.bind "lan" and auth token.

  Model id is taken from User/Process env JARVIS_OPENCLAW_GATEWAY_MODEL
  or defaults to ollama/qwen3:4b (local).

  Do NOT hardcode MiniMax or other cloud provider slugs here.
  Set the env var or edit the JSON after generation.

  For cloud credentials, edit manually:
  %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json
#>

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

function Write-OperatorEnvGuidance {
    Write-Host ""
    Write-Host "Where to set Windows User env vars (then open a new terminal):" -ForegroundColor DarkGray
    Write-Host "  - System Properties > Environment Variables, or PowerShell:" -ForegroundColor DarkGray
    Write-Host "    [Environment]::SetEnvironmentVariable(`"JARVIS_OPENCLAW_GATEWAY_MODEL`", `"<value>`", `"User`")" -ForegroundColor DarkGray
    Write-Host "    [Environment]::SetEnvironmentVariable(`"JARVIS_OPENCLAW_GATEWAY_TOKEN`", `"<value>`", `"User`")" -ForegroundColor DarkGray
    Write-Host "  - JARVIS_OPENCLAW_GATEWAY_MODEL : default agent model written into openclaw.json (cloud/local id per OpenClaw; not hardcoded in repo)." -ForegroundColor DarkGray
    Write-Host "  - JARVIS_OPENCLAW_GATEWAY_TOKEN : gateway HTTP auth token (required by this script)." -ForegroundColor DarkGray
    Write-Host "Cloud provider API keys / profiles (MiniMax, etc.):" -ForegroundColor DarkGray
    Write-Host "  %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json" -ForegroundColor DarkGray
    Write-Host "  Keep provider secrets outside git; see docs/MINIMAX_SETUP.md" -ForegroundColor DarkGray
}

Write-Step "=== JARVIS Phase 3: Configure OpenClaw ==="

$base = Join-Path $env:USERPROFILE ".openclaw"
$wsMain = Join-Path $base "workspace\main"
$wsMainJson = $wsMain.Replace("\", "\\")

# Gateway token MUST come from environment.
$gatewayToken = [Environment]::GetEnvironmentVariable("JARVIS_OPENCLAW_GATEWAY_TOKEN", "User")
if ([string]::IsNullOrWhiteSpace($gatewayToken)) {
    $gatewayToken = $env:JARVIS_OPENCLAW_GATEWAY_TOKEN
}

if ([string]::IsNullOrWhiteSpace($gatewayToken)) {
    Write-Fail "JARVIS_OPENCLAW_GATEWAY_TOKEN is not set."
    Write-Host "Set Windows User (or process) env JARVIS_OPENCLAW_GATEWAY_TOKEN, then re-run this script." -ForegroundColor DarkGray
    Write-Host "See docs/SECRET_ROTATION.md and docs/MINIMAX_SETUP.md." -ForegroundColor DarkGray
    Write-OperatorEnvGuidance
    exit 1
}

# Gateway agent model: use env or default to local Ollama.
$model = [Environment]::GetEnvironmentVariable("JARVIS_OPENCLAW_GATEWAY_MODEL", "User")
if ([string]::IsNullOrWhiteSpace($model)) {
    $model = $env:JARVIS_OPENCLAW_GATEWAY_MODEL
}

if ([string]::IsNullOrWhiteSpace($model)) {
    $model = "ollama/qwen3:4b"
    Write-Host "[INFO] JARVIS_OPENCLAW_GATEWAY_MODEL not set; defaulting to $model" -ForegroundColor Yellow
}

$json = @"
{
  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "lan",
    "auth": {
      "mode": "token",
      "token": "$gatewayToken"
    }
  },
  "agents": {
    "list": [
      {
        "id": "main",
        "default": true,
        "workspace": "$wsMainJson",
        "model": "$model"
      }
    ]
  }
}
"@

if (-not (Test-Path -LiteralPath $base)) {
    New-Item -ItemType Directory -Path $base -Force | Out-Null
}

$openclawPath = Join-Path $base "openclaw.json"
$configPath = Join-Path $base "config.json"

Set-Content -LiteralPath $openclawPath -Value $json.Trim() -Encoding UTF8
Set-Content -LiteralPath $configPath -Value $json.Trim() -Encoding UTF8

Write-Ok "Wrote $openclawPath"
Write-Ok "Wrote $configPath"

Write-Host ""
Write-Host "Gateway model in JSON: from JARVIS_OPENCLAW_GATEWAY_MODEL (or default ollama/... if unset). Guide: docs/MINIMAX_SETUP.md" -ForegroundColor DarkGray
Write-OperatorEnvGuidance

Write-Ok "Phase 3 configure finished."
exit 0
