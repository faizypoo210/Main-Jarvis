<#
.SYNOPSIS
  Writes %USERPROFILE%\.openclaw\openclaw.json and config.json (identical), with gateway.bind "lan" and auth token.
  Model id is taken from User/Process env JARVIS_OPENCLAW_GATEWAY_MODEL or defaults to ollama/qwen3:4b (local).
  Do NOT hardcode MiniMax or other cloud provider slugs here — set the env var or edit the JSON after generation.
  For cloud credentials, edit manually: %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json (per OpenClaw docs).
#>
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Step "=== JARVIS Phase 3: Configure OpenClaw (no doctor, no provider secrets in files) ==="

$base = Join-Path $env:USERPROFILE ".openclaw"
$wsMain = Join-Path $base "workspace\main"
$wsMainJson = $wsMain.Replace("\", "\\")

# Gateway token MUST come from environment — never from the repo (no embedded fallbacks).
$gatewayToken = [Environment]::GetEnvironmentVariable("JARVIS_OPENCLAW_GATEWAY_TOKEN", "User")
if ([string]::IsNullOrWhiteSpace($gatewayToken)) { $gatewayToken = $env:JARVIS_OPENCLAW_GATEWAY_TOKEN }
if ([string]::IsNullOrWhiteSpace($gatewayToken)) {
    Write-Fail "JARVIS_OPENCLAW_GATEWAY_TOKEN is not set."
    Write-Host "       Set a User environment variable JARVIS_OPENCLAW_GATEWAY_TOKEN (high-entropy secret), then re-run." -ForegroundColor DarkGray
    Write-Host "       OpenClaw will use it in %USERPROFILE%\.openclaw\openclaw.json. See docs/SECRET_ROTATION.md." -ForegroundColor DarkGray
    exit 1
}

# Gateway agent model: never guess MiniMax slug — use env or local Ollama default.
$model = [Environment]::GetEnvironmentVariable("JARVIS_OPENCLAW_GATEWAY_MODEL", "User")
if ([string]::IsNullOrWhiteSpace($model)) { $model = $env:JARVIS_OPENCLAW_GATEWAY_MODEL }
if ([string]::IsNullOrWhiteSpace($model)) {
    $model = "ollama/qwen3:4b"
    Write-Host "[INFO] JARVIS_OPENCLAW_GATEWAY_MODEL not set; defaulting to $model. For MiniMax 2.5 via OpenClaw, set User env to your provider/model id from OpenClaw docs, or edit openclaw.json." -ForegroundColor Yellow
}

# OpenClaw reads openclaw.json (JSON5-capable). Duplicate as config.json per JARVIS layout.
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
Set-Content -LiteralPath $openclawPath -Value $json.Trim() -Encoding utf8
Set-Content -LiteralPath $configPath -Value $json.Trim() -Encoding utf8
Write-Ok "Wrote $openclawPath and $configPath (same content)."

Write-Host ""
Write-Host "Manual step — cloud providers (e.g. MiniMax): add API keys / profiles in:" -ForegroundColor DarkGray
Write-Host "  %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json" -ForegroundColor DarkGray
Write-Host "Follow OpenClaw documentation for your provider; do not commit secrets to git." -ForegroundColor DarkGray

# TODO(MiniMax / cloud): Repo cannot automate provider auth. After setting JARVIS_OPENCLAW_GATEWAY_MODEL to your real
# provider/model id, manually complete %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json per OpenClaw docs; restart gateway.

Write-Ok "Phase 3 configure finished."
exit 0
