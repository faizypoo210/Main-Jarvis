#Requires -Version 5.1
<#
.SYNOPSIS
  Verify two-model runtime: Ollama local (qwen3:4b) vs OpenClaw gateway model and auth profile presence.

.DESCRIPTION
  This script checks **machine readiness** for local inference vs OpenClaw/gateway. It does **not** assert
  mission routing (`routing_decided`) or executor `lane_truth` — use `11-smoke-model-lanes.ps1` with the
  full stack for that. Canonical vocabulary: docs/MODEL_LANES.md.

.PARAMETER Startup
  If set, never exit non-zero; print WARN for gaps (for jarvis.ps1 preflight).
#>
param(
    [switch]$Startup
)

$ErrorActionPreference = 'Stop'

$OLLAMA_DEFAULT = 'qwen3:4b'
if (-not [string]::IsNullOrWhiteSpace($env:OLLAMA_MODEL)) {
    $OLLAMA_DEFAULT = $env:OLLAMA_MODEL.Trim()
}

$script:fail = 0
$script:warn = 0

function Pass([string]$m) { Write-Host "[PASS] $m" -ForegroundColor Green }
function Warn([string]$m) {
    Write-Host "[WARN] $m" -ForegroundColor Yellow
    $script:warn = [int]$script:warn + 1
}
function Fail([string]$m) {
    if ($Startup) {
        Write-Host "[WARN] $m" -ForegroundColor Yellow
        $script:warn = [int]$script:warn + 1
    } else {
        Write-Host "[FAIL] $m" -ForegroundColor Red
        $script:fail = [int]$script:fail + 1
    }
}

function Read-OpenClawGatewayModel {
    $p = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
    if (-not (Test-Path -LiteralPath $p)) {
        return @{ Ok = $false; Path = $p; Model = $null; Error = 'file missing' }
    }
    try {
        $raw = Get-Content -LiteralPath $p -Raw -Encoding UTF8
        $j = $raw | ConvertFrom-Json
        if (-not $j.agents -or -not $j.agents.list) {
            return @{ Ok = $true; Path = $p; Model = $null; Error = 'no agents.list' }
        }
        $list = @($j.agents.list)
        foreach ($a in $list) {
            if ($a.default -eq $true -and $a.model) {
                return @{ Ok = $true; Path = $p; Model = [string]$a.model; Error = $null }
            }
        }
        return @{ Ok = $true; Path = $p; Model = $null; Error = 'no default agent model' }
    } catch {
        return @{ Ok = $false; Path = $p; Model = $null; Error = $_.Exception.Message }
    }
}

function Test-AuthProfilesObject {
    $p = Join-Path $env:USERPROFILE '.openclaw\agents\main\agent\auth-profiles.json'
    if (-not (Test-Path -LiteralPath $p)) {
        return @{ Present = $false; Path = $p; NonEmpty = $false }
    }
    try {
        $raw = Get-Content -LiteralPath $p -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($raw) -or $raw.Length -lt 3) {
            return @{ Present = $true; Path = $p; NonEmpty = $false }
        }
        $o = $raw | ConvertFrom-Json
        $ne = $false
        if ($o -is [hashtable]) { $ne = $o.Count -gt 0 }
        elseif ($o.PSObject.Properties.Count -gt 0) { $ne = $true }
        return @{ Present = $true; Path = $p; NonEmpty = $ne }
    } catch {
        return @{ Present = $true; Path = $p; NonEmpty = $false }
    }
}

Write-Host "=== 11-verify-model-lanes ===" -ForegroundColor Cyan
Write-Host "Readiness: Ollama + OpenClaw CLI + gateway HTTP + openclaw.json model. For mission routing + receipt lane_truth coherence, run: .\scripts\11-smoke-model-lanes.ps1" -ForegroundColor DarkGray

# Ollama HTTP
try {
    $r = Invoke-WebRequest -Uri 'http://localhost:11434' -UseBasicParsing -TimeoutSec 8
    if ($r.StatusCode -eq 200) { Pass "Ollama HTTP (11434)" }
    else { Fail "Ollama HTTP returned $($r.StatusCode)" }
} catch {
    Fail "Ollama not reachable on 11434: $_"
}

# ollama list contains model
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    $listOut = & ollama list 2>&1 | Out-String
    if ($listOut -match [regex]::Escape($OLLAMA_DEFAULT)) {
        Pass "Ollama model present: $OLLAMA_DEFAULT"
    } else {
        Warn "Model '$OLLAMA_DEFAULT' not listed in 'ollama list'. Pull: ollama pull $OLLAMA_DEFAULT"
    }
} else {
    Warn "ollama CLI not on PATH; cannot verify local model tag."
}

# OpenClaw CLI
if (Get-Command openclaw -ErrorAction SilentlyContinue) {
    $st = & openclaw status 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        Pass "openclaw status (exit 0)"
    } else {
        Fail "openclaw status failed (exit $LASTEXITCODE)"
    }
} else {
    Fail "openclaw CLI not found on PATH"
}

# Gateway HTTP
try {
    $gr = Invoke-WebRequest -Uri 'http://localhost:18789' -UseBasicParsing -TimeoutSec 10
    if ($gr.StatusCode -eq 200) { Pass "OpenClaw gateway HTTP (18789)" }
    else { Warn "Gateway HTTP $($gr.StatusCode)" }
} catch {
    Warn "OpenClaw gateway not reachable on 18789 (start gateway if you need cloud lane): $_"
}

# openclaw.json default model
$oc = Read-OpenClawGatewayModel
if (-not $oc.Ok) {
    Fail "Cannot read gateway model: $($oc.Path) - $($oc.Error)"
} elseif ([string]::IsNullOrWhiteSpace($oc.Model)) {
    Warn "No default agent model in openclaw.json ($($oc.Path)). Set JARVIS_OPENCLAW_GATEWAY_MODEL or edit JSON."
} else {
    Pass "Gateway model string: $($oc.Model)"
    $m = $oc.Model.ToLowerInvariant()
    if ($m.StartsWith('ollama/')) {
        Pass "Gateway lane classification: local (OpenClaw -> Ollama)"
    } else {
        Pass "Gateway lane classification: cloud/other (not ollama/ prefix)"
        $ap = Test-AuthProfilesObject
        if (-not $ap.Present) {
            Warn "auth-profiles.json missing at $($ap.Path). Cloud execution usually requires provider entries (edit manually per OpenClaw docs)."
        } elseif (-not $ap.NonEmpty) {
            Warn "auth-profiles.json exists but appears empty or invalid. Cloud lane may not be authenticated."
        } else {
            Pass "auth-profiles.json present with at least one top-level key (no secrets printed)"
        }
    }
}

Write-Host ""
if ($Startup) {
    Write-Host "Model-lane preflight complete (Startup mode: exit 0). FAIL=$($script:fail) WARN=$($script:warn)" -ForegroundColor Cyan
    exit 0
}

if ($script:fail -gt 0) {
    Write-Host "Result: FAIL ($($script:fail) hard failure(s), $($script:warn) warning(s))" -ForegroundColor Red
    exit 1
}
Write-Host "Result: OK ($($script:warn) warning(s))" -ForegroundColor Green
exit 0
