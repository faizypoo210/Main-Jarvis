#Requires -Version 5.1
# Phase 6: Write TOOLS.md to the main agent workspace and enable composio in openclaw.json (merge only plugins.entries.composio).
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Web.Extensions

$workspaceMain = Join-Path $env:USERPROFILE '.openclaw\workspace\main'
if (-not (Test-Path $workspaceMain)) {
    New-Item -ItemType Directory -Path $workspaceMain -Force | Out-Null
}

$toolsMd = Join-Path $workspaceMain 'TOOLS.md'
$toolsContent = @'
# TOOLS.md — Available Integrations

## Connected via Composio

- Gmail: read emails, send emails, search inbox
- Google Calendar: read events, create events, check availability
- Slack: send messages, read channels, post updates
- Notion: read pages, create pages, update databases
- GitHub: read repos, create issues, check PRs, push code

## Usage Rules

- Always confirm before sending emails or messages on my behalf
- Always confirm before creating calendar events
- GitHub actions that modify code require explicit approval
- Notion writes require explicit approval
- Reading and searching is always permitted without approval
'@
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($toolsMd, $toolsContent, $utf8NoBom)
Write-Host "Wrote $toolsMd"

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
$entries['composio'] = @{
    enabled = $true
}

$out = $ser.Serialize($obj)
[System.IO.File]::WriteAllText($path, $out, $utf8NoBom)

Write-Host "Updated openclaw.json: $path (plugins.entries.composio.enabled = true)"
Write-Host ""
Write-Host "--- plugins (excerpt) ---"
Write-Host ($ser.Serialize($obj['plugins']))
