#Requires -Version 5.1
# Phase 6: Connect Gmail, Google Calendar, Slack, Notion, GitHub via composio add (OAuth in browser; continues on failure).
$ErrorActionPreference = 'Continue'

if (-not (Get-Command composio -ErrorAction SilentlyContinue)) {
    throw "composio CLI not found. Run 06-install-composio.ps1 first."
}

if (-not $env:COMPOSIO_API_KEY) {
    Write-Warning "COMPOSIO_API_KEY is not set in this session. composio-core may require it (get a key at https://app.composio.dev/settings). Connection attempts may fail until it is set in your user environment."
}

$services = @(
    @{ Display = 'Gmail'; App = 'gmail' },
    @{ Display = 'Google Calendar'; App = 'googlecalendar' },
    @{ Display = 'Slack'; App = 'slack' },
    @{ Display = 'Notion'; App = 'notion' },
    @{ Display = 'GitHub'; App = 'github' }
)

$success = New-Object System.Collections.Generic.List[string]
$failed = New-Object System.Collections.Generic.List[string]

foreach ($s in $services) {
    Write-Host ""
    Write-Host "Connecting $($s.Display)... A browser window will open."
    Write-Host "Complete the OAuth flow, then return here."

    $exitCode = 0
    $output = ''
    try {
        $output = & composio add $s.App 2>&1 | ForEach-Object { $_ } | Out-String
        Write-Host $output
        $exitCode = $LASTEXITCODE
    } catch {
        $output += $_.Exception.Message
        $exitCode = 1
    }

    if ($exitCode -eq 0 -and $output -notmatch 'Operation cancelled') {
        Write-Host "SUCCESS: $($s.Display) ($($s.App)) connection step finished."
        $success.Add($s.Display)
    } else {
        Write-Host "FAILED or SKIPPED: $($s.Display) ($($s.App)) connection step (exit $exitCode)."
        $failed.Add($s.Display)
    }
}

Write-Host ""
Write-Host "========== Summary =========="
Write-Host "Succeeded or completed: $($success -join ', ')"
if ($failed.Count -gt 0) {
    Write-Host "Failed or skipped: $($failed -join ', ')"
} else {
    Write-Host "Failed or skipped: (none)"
}
