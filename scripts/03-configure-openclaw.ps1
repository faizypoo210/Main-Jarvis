<#
.SYNOPSIS
  Writes %USERPROFILE%\.openclaw\openclaw.json and config.json (identical), with gateway.bind "lan" and auth token; prompts for Anthropic API key and persists only to User environment (not files).
#>
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Step "=== JARVIS Phase 3: Configure OpenClaw (no doctor, no key in files) ==="

$base = Join-Path $env:USERPROFILE ".openclaw"
$wsMain = Join-Path $base "workspace\main"
$wsMainJson = $wsMain.Replace("\", "\\")

$gatewayToken = "1aa716114e74097698e1ffe4be8d550f181f291afa1b86db"

# OpenClaw reads openclaw.json (JSON5-capable). Duplicate as config.json per JARVIS spec.
# gateway.bind is the bind mode keyword "lan" (not an IP). gateway.host is not a separate schema field when bind is lan.
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
        "model": "gpt-5"
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

if (-not [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")) {
    $key = Read-Host "Enter your OpenAI API key" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($key))
    [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", $plain, "User")
    Write-Host "OPENAI_API_KEY saved to User environment."
} else {
    Write-Host "OPENAI_API_KEY already set, skipping."
}

Write-Ok "Phase 3 configure finished."
exit 0
