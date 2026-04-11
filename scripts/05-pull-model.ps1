#Requires -Version 5.1
# Phase 5: Pull default local model into Ollama (GPU-capable Ollama install; no CPU-only override).
# Set OLLAMA_MODEL (User or session) to override; default qwen3:4b.
$ErrorActionPreference = 'Stop'

$Model = [Environment]::GetEnvironmentVariable('OLLAMA_MODEL', 'User')
if ([string]::IsNullOrWhiteSpace($Model)) { $Model = $env:OLLAMA_MODEL }
if ([string]::IsNullOrWhiteSpace($Model)) { $Model = 'qwen3:4b' }

$listen = @(Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)
if ($listen.Count -eq 0) {
    throw "Ollama is not listening on port 11434. Run 05-start-ollama.ps1 first."
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "ollama command not found."
}

Write-Host "Pulling model $Model (OLLAMA_MODEL; this may take several minutes depending on network and disk)..."
& ollama pull $Model
if (-not $?) {
    throw "ollama pull $Model failed."
}

$listOut = & ollama list 2>&1
Write-Host $listOut
$text = $listOut | Out-String
# Escape regex special chars in model tag (e.g. qwen3:4b — ':' is not special in .NET regex for -match)
if ($text -notmatch [regex]::Escape($Model)) {
    throw "$Model was not found in ollama list output after pull."
}

Write-Host "$Model is present. Pull completed successfully."
exit 0
