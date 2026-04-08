#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$SourceJson = Join-Path $RepoRoot 'config\jarvis-dashboard.json'
$LobsterRoot = 'C:\projects\LobsterBoard'
$TemplateDir = Join-Path $LobsterRoot 'templates\jarvis-dashboard'

if (-not (Test-Path $SourceJson)) {
    throw "Missing config file: $SourceJson"
}
if (-not (Test-Path $LobsterRoot)) {
    throw "LobsterBoard not found at $LobsterRoot - run 04-install-lobsterboard.ps1 first."
}

New-Item -ItemType Directory -Path $TemplateDir -Force | Out-Null

$raw = Get-Content -Path $SourceJson -Raw -Encoding UTF8
$doc = $raw | ConvertFrom-Json

if (-not $doc.lobsterBoard) {
    throw "jarvis-dashboard.json must contain a 'lobsterBoard' object with canvas and widgets."
}

$destJarvis = Join-Path $TemplateDir 'jarvis-dashboard.json'
Copy-Item -Path $SourceJson -Destination $destJarvis -Force

$dashboardJson = $doc.lobsterBoard | ConvertTo-Json -Depth 30
$configPath = Join-Path $TemplateDir 'config.json'
Set-Content -Path $configPath -Value $dashboardJson -Encoding UTF8

$widgetCount = 0
if ($doc.lobsterBoard.widgets) {
    $widgetCount = @($doc.lobsterBoard.widgets).Count
}

$meta = [ordered]@{
    id            = 'jarvis-dashboard'
    name          = 'JARVIS'
    description   = 'Mission Control, OpenClaw Gateway, DashClaw, and local system stats (see jarvis-dashboard.json for REST/Bearer specs).'
    author        = 'JARVIS'
    tags          = @('jarvis', 'mission-control', 'openclaw', 'dashclaw')
    canvasSize    = '1920x1080'
    widgetCount   = $widgetCount
    requiresSetup = @()
}
$metaPath = Join-Path $TemplateDir 'meta.json'
($meta | ConvertTo-Json -Depth 10) | Set-Content -Path $metaPath -Encoding UTF8

Write-Host "Wrote template to $TemplateDir (jarvis-dashboard.json, config.json, meta.json)."
