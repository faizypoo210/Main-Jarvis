#Requires -Version 5.1
<#
.SYNOPSIS
  Copies governed OpenClaw workspace markdown from this repo into %USERPROFILE%\.openclaw\workspace\main\

.DESCRIPTION
  Source of truth for *which* files: config\workspace\governance-manifest.json (sync_order + required_files).
  Persona / policy / context only - not mission state. Never touches auth-profiles.json, openclaw.json, or paths outside workspace\main for approved .md files.

  Creates a timestamped backup of any destination file before overwrite.

  Canonical operator file: USERS.md (not USER.md).
#>
$ErrorActionPreference = 'Stop'

$JarvisRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$SrcDir = Join-Path $JarvisRoot 'config\workspace'
$DstDir = Join-Path $env:USERPROFILE '.openclaw\workspace\main'
$ManifestPath = Join-Path $SrcDir 'governance-manifest.json'

$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupDir = Join-Path $DstDir (Join-Path '.jarvis-sync-backups' "pre-sync-$ts")

function Get-FileSha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

Write-Host "=== JARVIS: sync OpenClaw workspace (repo -> live) ===" -ForegroundColor Cyan
Write-Host "Repo source dir: $SrcDir"
Write-Host "Live destination: $DstDir"
Write-Host "Manifest:        $ManifestPath"
Write-Host "Backup folder:   $BackupDir"
Write-Host ""

if (-not (Test-Path -LiteralPath $SrcDir)) {
    throw "Source directory missing: $SrcDir"
}
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "governance-manifest.json missing: $ManifestPath"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$syncOrder = @($manifest.sync_order)
$required = @($manifest.required_files)
$optional = @()
if ($manifest.optional_files) { $optional = @($manifest.optional_files) }

$failedReq = $false
foreach ($req in $required) {
    $p = Join-Path $SrcDir $req
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Host "[FAIL] Required source missing: $req (expected $p)" -ForegroundColor Red
        $failedReq = $true
    }
}
if ($failedReq) {
    Write-Host ""
    Write-Host "Fix missing files in config\workspace or restore from git. Sync aborted." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath $DstDir)) {
    New-Item -ItemType Directory -Path $DstDir -Force | Out-Null
    Write-Host "[INFO] Created destination directory: $DstDir" -ForegroundColor DarkGray
}

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

$userDrift = Join-Path $SrcDir 'USER.md'
if (Test-Path -LiteralPath $userDrift) {
    Write-Host "[WARN] USER.md exists in config\workspace - canonical name is USERS.md; remove or rename to avoid drift." -ForegroundColor Yellow
}

$copied = 0
$skippedMissingSrc = 0
$unchanged = 0

foreach ($name in $syncOrder) {
    $src = Join-Path $SrcDir $name
    $dst = Join-Path $DstDir $name

    if (-not (Test-Path -LiteralPath $src)) {
        $isOpt = $optional -contains $name
        if ($isOpt) {
            Write-Host "[SKIP] $name (optional, not in repo)" -ForegroundColor DarkYellow
        } else {
            Write-Host "[MISSING-SOURCE] $name - listed in sync_order but absent; add at: $src" -ForegroundColor Yellow
        }
        $skippedMissingSrc++
        continue
    }

    $srcHash = Get-FileSha256 $src
    $dstHash = if (Test-Path -LiteralPath $dst) { Get-FileSha256 $dst } else { $null }

    if ($null -ne $dstHash -and $srcHash -eq $dstHash) {
        Write-Host "[UNCHANGED] $name (hash matches live copy)" -ForegroundColor DarkGray
        $unchanged++
        continue
    }

    if (Test-Path -LiteralPath $dst) {
        $bakPath = Join-Path $BackupDir $name
        Copy-Item -LiteralPath $dst -Destination $bakPath -Force
        Write-Host "[BACKUP] $name -> $bakPath" -ForegroundColor DarkGray
    } else {
        Write-Host "[NEW] $name (no previous file at destination)" -ForegroundColor DarkGray
    }

    Copy-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "[UPDATED] $name" -ForegroundColor Green
    $copied++
}

Write-Host ""
Write-Host "Summary: updated=$copied unchanged=$unchanged missing-or-skipped=$skippedMissingSrc" -ForegroundColor Cyan
Write-Host "Not copied: governance-manifest.json (audit/sync metadata only)." -ForegroundColor DarkGray
Write-Host "Secrets not touched: agents/*/auth-profiles.json, openclaw.json, config.json, etc." -ForegroundColor DarkGray

Write-Host ""
Write-Host "TODO: Configure cloud credentials in auth-profiles.json if not already done." -ForegroundColor Yellow

exit 0
