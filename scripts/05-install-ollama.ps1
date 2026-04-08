#Requires -Version 5.1
# Phase 5: Detect Ollama CLI; manual install required if missing.
$ErrorActionPreference = 'Stop'

$cmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($cmd) {
    try {
        $ver = & ollama --version 2>&1
        Write-Host "Ollama is already installed."
        Write-Host $ver
    } catch {
        Write-Host "Ollama is already installed (Get-Command found: $($cmd.Source))."
    }
    exit 0
}

Write-Host @"
Ollama is not installed. Please install it manually:
1. Go to https://ollama.com/download
2. Download the Windows installer (.exe)
3. Run the installer and follow the prompts
4. After install, restart PowerShell and re-run this script to confirm ollama is detected.
"@
exit 0
