#Requires -Version 5.1
# Phase 5: Verify Ollama service, phi4-mini, API generate, and OpenClaw Ollama plugin entry.
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Web.Extensions

function Test-OllamaListening {
    $c = @(Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)
    return ($c.Count -gt 0)
}

if (-not (Test-OllamaListening)) {
    throw "Port 11434 is not listening."
}

try {
    $resp = Invoke-WebRequest -Uri 'http://localhost:11434' -UseBasicParsing -TimeoutSec 15
} catch {
    throw "HTTP GET http://localhost:11434 failed: $_"
}
if ($resp.StatusCode -ne 200) {
    throw "Expected HTTP 200 from http://localhost:11434, got $($resp.StatusCode)."
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "ollama command not found."
}

$listOut = & ollama list 2>&1
Write-Host "--- ollama list ---"
Write-Host $listOut
$text = $listOut | Out-String
if ($text -notmatch 'phi4-mini') {
    throw "phi4-mini not found in ollama list."
}

$body = @{
    model  = 'phi4-mini'
    prompt = 'Say: Jarvis local model online.'
    stream = $false
} | ConvertTo-Json -Compress

Write-Host ""
Write-Host "--- POST /api/generate (test prompt) ---"
try {
    $gen = Invoke-RestMethod -Uri 'http://localhost:11434/api/generate' -Method Post -Body $body -ContentType 'application/json; charset=utf-8' -TimeoutSec 600
} catch {
    throw "POST /api/generate failed: $_"
}
$genJson = $gen | ConvertTo-Json -Depth 10 -Compress
Write-Host $genJson

$path = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
if (-not (Test-Path $path)) {
    throw "OpenClaw config missing: $path"
}

$raw = Get-Content -Path $path -Raw -Encoding UTF8
$ser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
$ser.MaxJsonLength = 67108864
$cfg = $ser.DeserializeObject($raw)

$ok = $false
if ($cfg -and $cfg.ContainsKey('plugins')) {
    $p = $cfg['plugins']
    if ($p -and $p.ContainsKey('entries')) {
        $e = $p['entries']
        if ($e -and $e.ContainsKey('ollama')) {
            $o = $e['ollama']
            if ($o -and $o.ContainsKey('enabled') -and [bool]$o['enabled']) {
                $ok = $true
            }
        }
    }
}
if (-not $ok) {
    throw "OpenClaw openclaw.json does not have plugins.entries.ollama.enabled = true."
}

Write-Host ""
Write-Host "All Phase 5 verification checks passed."
exit 0
