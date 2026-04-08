#Requires -Version 5.1
# Phase 5: Ensure Ollama binds on LAN (OLLAMA_HOST=0.0.0.0:11434) and is serving.
$ErrorActionPreference = 'Stop'

function Test-OllamaListening {
    $c = @(Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)
    return ($c.Count -gt 0)
}

if (Test-OllamaListening) {
    Write-Host "Ollama is already listening on port 11434."
    exit 0
}

$proc = Get-Process -Name 'ollama' -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "Ollama process is running but port 11434 is not listening yet; waiting..."
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        if (Test-OllamaListening) {
            Write-Host "Ollama is now listening on port 11434."
            exit 0
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Ollama process exists but port 11434 did not become available within 15 seconds."
}

$ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $ollamaExe) {
    throw "ollama command not found. Run 05-install-ollama.ps1 and install Ollama manually first."
}

$env:OLLAMA_HOST = '0.0.0.0:11434'
Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
    if (Test-OllamaListening) {
        Write-Host "Ollama started (OLLAMA_HOST=0.0.0.0:11434) and is listening on port 11434."
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

throw "Ollama did not start listening on port 11434 within 15 seconds."
