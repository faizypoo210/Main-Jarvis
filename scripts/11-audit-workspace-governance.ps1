#Requires -Version 5.1
<#
.SYNOPSIS
  Audits the Jarvis workspace governance pack: required files, manifest consistency, filename drift.

.DESCRIPTION
  Exit 0 = no FAIL; exit 1 = missing required files or manifest/sync mismatch.

  Run: .\scripts\11-audit-workspace-governance.ps1
#>
$ErrorActionPreference = 'Stop'

$JarvisRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WsDir = Join-Path $JarvisRoot 'config\workspace'
$ManifestPath = Join-Path $WsDir 'governance-manifest.json'
$SyncScript = Join-Path $JarvisRoot 'scripts\10-sync-openclaw-workspace.ps1'
$DocFiles = Join-Path $JarvisRoot 'docs\OPENCLAW_WORKSPACE_FILES.md'

$warn = 0
$fail = 0
$notes = New-Object System.Collections.ArrayList

function Add-Note([string]$line) { [void]$notes.Add($line) }

Write-Host "=== JARVIS: workspace governance audit ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    Write-Host "[FAIL] governance-manifest.json missing: $ManifestPath" -ForegroundColor Red
    exit 1
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$required = @($manifest.required_files)
$syncOrder = @($manifest.sync_order)

# Required files: exist, heading, minimal size
foreach ($f in $required) {
    $p = Join-Path $WsDir $f
    if (-not (Test-Path -LiteralPath $p)) {
        Add-Note "FAIL: missing required file: $f"
        $fail++
        continue
    }
    $len = (Get-Item -LiteralPath $p).Length
    if ($len -lt 40) {
        Add-Note "WARN: $f is very short ($len bytes)"
        $warn++
    }
    $head = Get-Content -LiteralPath $p -TotalCount 1 -ErrorAction SilentlyContinue
    if ($head -notmatch '^\s*#') {
        Add-Note "WARN: $f - first line should be a markdown heading (# ...)"
        $warn++
    } else {
        Add-Note "OK: $f"
    }
}

# sync_order must include every required file (same set)
foreach ($r in $required) {
    if ($syncOrder -notcontains $r) {
        Add-Note "FAIL: required file not in sync_order: $r"
        $fail++
    }
}
foreach ($s in $syncOrder) {
    if ($required -notcontains $s) {
        Add-Note "WARN: sync_order lists $s but it is not in required_files"
        $warn++
    }
}

# USER.md drift (canonical is USERS.md)
$userBad = Join-Path $WsDir 'USER.md'
if (Test-Path -LiteralPath $userBad) {
    Add-Note "WARN: USER.md present - canonical is USERS.md; remove or rename"
    $warn++
}

# Sync script reads manifest
if (-not (Test-Path -LiteralPath $SyncScript)) {
    Add-Note "FAIL: sync script missing: $SyncScript"
    $fail++
} else {
    $syncText = Get-Content -LiteralPath $SyncScript -Raw
    if ($syncText -notmatch 'governance-manifest\.json') {
        Add-Note "FAIL: sync script must load governance-manifest.json"
        $fail++
    } else {
        Add-Note "OK: sync script loads governance-manifest.json"
    }
}

# Doc present and mentions manifest + canonical filenames
if (-not (Test-Path -LiteralPath $DocFiles)) {
    Add-Note "WARN: docs/OPENCLAW_WORKSPACE_FILES.md missing"
    $warn++
} else {
    $d = Get-Content -LiteralPath $DocFiles -Raw
    if ($d -notmatch 'governance-manifest') {
        Add-Note "WARN: OPENCLAW_WORKSPACE_FILES.md should document governance-manifest.json"
        $warn++
    }
    if ($d -notmatch 'USERS\.md') {
        Add-Note "WARN: OPENCLAW_WORKSPACE_FILES.md should document USERS.md"
        $warn++
    }
    if ($d -notmatch 'HEARTBEAT\.md') {
        Add-Note "WARN: OPENCLAW_WORKSPACE_FILES.md should document HEARTBEAT.md"
        $warn++
    }
}

Write-Host "Notes:" -ForegroundColor Cyan
foreach ($n in $notes) {
    $c = 'Gray'
    if ($n -match '^FAIL') { $c = 'Red' }
    elseif ($n -match '^WARN') { $c = 'Yellow' }
    elseif ($n -match '^OK') { $c = 'DarkGreen' }
    Write-Host "  $n" -ForegroundColor $c
}

Write-Host ""
if ($fail -gt 0) {
    Write-Host "AUDIT: FAIL ($fail)" -ForegroundColor Red
    exit 1
}
if ($warn -gt 0) {
    Write-Host "AUDIT: PASS with $warn warning(s)" -ForegroundColor Yellow
    exit 0
}
Write-Host "AUDIT: PASS" -ForegroundColor Green
exit 0
