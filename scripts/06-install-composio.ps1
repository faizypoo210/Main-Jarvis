#Requires -Version 5.1
# Phase 6: Install Composio CLI globally and @composio/openclaw-plugin under %USERPROFILE%\.openclaw (no secrets written to repo).
$ErrorActionPreference = 'Stop'

function Test-ComposioCli {
    return $null -ne (Get-Command composio -ErrorAction SilentlyContinue)
}

if (-not (Test-ComposioCli)) {
    Write-Host "Installing composio-core globally (npm install -g composio-core)..."
    npm install -g composio-core
    if (-not (Test-ComposioCli)) {
        throw "composio command not found after npm install -g composio-core."
    }
} else {
    Write-Host "composio CLI is already on PATH."
}

$npmList = npm list -g composio-core --depth=0 2>&1 | Out-String
Write-Host $npmList.Trim()

$openclawRoot = Join-Path $env:USERPROFILE '.openclaw'
if (-not (Test-Path $openclawRoot)) {
    New-Item -ItemType Directory -Path $openclawRoot -Force | Out-Null
}

$pkgJson = Join-Path $openclawRoot 'package.json'
if (-not (Test-Path $pkgJson)) {
    Write-Host "Creating minimal package.json in $openclawRoot (npm init cannot name a package '.openclaw')..."
    $minimal = @'
{
  "name": "openclaw-local",
  "version": "1.0.0",
  "private": true
}
'@
    Set-Content -Path $pkgJson -Value $minimal.Trim() -Encoding UTF8
}

$pluginPath = Join-Path $openclawRoot 'node_modules\@composio\openclaw-plugin'
if (-not (Test-Path $pluginPath)) {
    Write-Host "Installing @composio/openclaw-plugin in $openclawRoot ..."
    Push-Location $openclawRoot
    try {
        npm install @composio/openclaw-plugin
    } finally {
        Pop-Location
    }
} else {
    Write-Host "@composio/openclaw-plugin is already installed under $openclawRoot ."
}

if (-not (Test-Path $pluginPath)) {
    throw "Expected directory not found after install: $pluginPath"
}

Write-Host "Composio CLI and OpenClaw plugin install verification succeeded."
