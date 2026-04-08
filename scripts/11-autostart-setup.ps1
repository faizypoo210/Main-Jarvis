#Requires -Version 5.1
# Register a Windows Scheduled Task to run jarvis.ps1 at user logon.
$ErrorActionPreference = 'Stop'

$TaskName = 'JARVIS Startup'
$Description = 'Start all JARVIS services on login'
$JarvisRoot = Split-Path -Parent $PSScriptRoot
$JarvisPs1 = Join-Path $JarvisRoot 'jarvis.ps1'

if (-not (Test-Path -LiteralPath $JarvisPs1)) {
    throw "jarvis.ps1 not found: $JarvisPs1"
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$arg = "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$JarvisPs1`""
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg -WorkingDirectory $JarvisRoot
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $account
$Principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Description $Description `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings | Out-Null

Write-Host 'JARVIS auto-start registered. Will run on next login.' -ForegroundColor Green
