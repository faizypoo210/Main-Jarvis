#Requires -Version 5.1
# Phase 7: Create idempotent inbound TCP firewall rules on Private profile for JARVIS LAN access (requires Administrator).
$ErrorActionPreference = 'Stop'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "This script must be run as Administrator. Right-click PowerShell and choose Run as administrator, then re-run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -ForegroundColor Yellow
    exit 1
}

$rules = @(
    @{ DisplayName = 'JARVIS-MissionControl-UI';     Port = 3000 },
    @{ DisplayName = 'JARVIS-MissionControl-API';    Port = 3001 },
    @{ DisplayName = 'JARVIS-OpenClaw-Gateway';     Port = 18789 },
    @{ DisplayName = 'JARVIS-LobsterBoard';         Port = 8080 },
    @{ DisplayName = 'JARVIS-Ollama';               Port = 11434 }
)

foreach ($r in $rules) {
    $existing = @(Get-NetFirewallRule -DisplayName $r.DisplayName -ErrorAction SilentlyContinue)
    if ($existing.Count -gt 0) {
        Write-Host "Exists (skip): $($r.DisplayName) TCP $($r.Port)"
        continue
    }
    Write-Host "Creating: $($r.DisplayName) inbound TCP $($r.Port) (Private profile only)..."
    New-NetFirewallRule -DisplayName $r.DisplayName `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $r.Port `
        -Action Allow `
        -Profile Private `
        -Enabled True | Out-Null
}

Write-Host ""
Write-Host "========== JARVIS firewall rules (summary) ==========" -ForegroundColor Cyan
Get-NetFirewallRule | Where-Object { $_.DisplayName -like 'JARVIS-*' } | Sort-Object DisplayName | ForEach-Object {
    $rule = $_
    $pf = $_ | Get-NetFirewallPortFilter
    $ports = if ($pf.LocalPort) { ($pf.LocalPort -join ',') } else { '(any)' }
    Write-Host ("{0,-32} Port={1,-8} Enabled={2}" -f $rule.DisplayName, $ports, $rule.Enabled)
}
Write-Host "Done."
