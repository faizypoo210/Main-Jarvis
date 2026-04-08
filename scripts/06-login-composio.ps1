#Requires -Version 5.1
# Phase 6: Log in to Composio (browser opens; blocks until the CLI finishes).
$ErrorActionPreference = 'Stop'

if (-not (Get-Command composio -ErrorAction SilentlyContinue)) {
    throw "composio CLI not found. Run 06-install-composio.ps1 first."
}

Write-Host @"
A browser window will open for Composio login.
Complete the login, then return to this terminal.

If login fails or composio add later reports 'API Key is not provided':
  Set a user environment variable COMPOSIO_API_KEY from https://app.composio.dev/settings
  (this is not stored in the JARVIS repo), open a new PowerShell, then re-run 06-connect-services.ps1.
"@

& composio login
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Warning "composio login exited with code $code. Set COMPOSIO_API_KEY if the CLI requires it, then continue with 06-connect-services.ps1."
    exit $code
}
Write-Host "composio login completed."
