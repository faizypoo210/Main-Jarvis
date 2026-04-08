#Requires -Version 5.1
# Phase 5: Pull phi4-mini into Ollama (requires GPU-capable Ollama install; no CPU-only override).
$ErrorActionPreference = 'Stop'

$listen = @(Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)
if ($listen.Count -eq 0) {
    throw "Ollama is not listening on port 11434. Run 05-start-ollama.ps1 first."
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "ollama command not found."
}

Write-Host "Pulling model phi4-mini (this may take several minutes depending on network and disk)..."
& ollama pull phi4-mini
if (-not $?) {
    throw "ollama pull phi4-mini failed."
}

$listOut = & ollama list 2>&1
Write-Host $listOut
$text = $listOut | Out-String
if ($text -notmatch 'phi4-mini') {
    throw "phi4-mini was not found in ollama list output after pull."
}

Write-Host "phi4-mini is present. Pull completed successfully."
exit 0
