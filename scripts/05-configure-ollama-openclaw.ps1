#Requires -Version 5.1
# Phase 5: Add Ollama plugin entry to OpenClaw after model is verified (does not change primary agent model).
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Web.Extensions

$path = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
if (-not (Test-Path $path)) {
    throw "OpenClaw config not found: $path"
}

$raw = Get-Content -Path $path -Raw -Encoding UTF8
$ser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
$ser.MaxJsonLength = 67108864
$obj = $ser.DeserializeObject($raw)

if (-not $obj) { throw "Failed to parse openclaw.json." }

if (-not $obj.ContainsKey('plugins')) {
    $obj['plugins'] = @{}
}
$plugins = $obj['plugins']
if (-not $plugins.ContainsKey('entries')) {
    $plugins['entries'] = @{}
}
$entries = $plugins['entries']
$entries['ollama'] = @{
    enabled = $true
    baseUrl = 'http://localhost:11434'
}

$out = $ser.Serialize($obj)
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($path, $out, $utf8NoBom)

Write-Host "Updated openclaw.json: $path"
Write-Host ""
Write-Host "--- agents (unchanged primary model) ---"
if ($obj.ContainsKey('agents')) {
    $agentsJson = $ser.Serialize($obj['agents'])
    Write-Host $agentsJson
} else {
    Write-Host "(no agents section)"
}
Write-Host ""
Write-Host "--- plugins ---"
if ($obj.ContainsKey('plugins')) {
    $pluginsJson = $ser.Serialize($obj['plugins'])
    Write-Host $pluginsJson
} else {
    Write-Host "(no plugins section)"
}
