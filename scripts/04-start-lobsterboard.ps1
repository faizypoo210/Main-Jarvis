#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$LobsterRoot = 'C:\projects\LobsterBoard'
$LogFile = Join-Path $LobsterRoot 'lobsterboard.log'

if (-not (Test-Path $LobsterRoot)) {
    throw "LobsterBoard not found at $LobsterRoot - run 04-install-lobsterboard.ps1 first."
}
$serverCjs = Join-Path $LobsterRoot 'server.cjs'
if (-not (Test-Path $serverCjs)) {
    throw "server.cjs missing at $serverCjs."
}

# Stop anything listening on TCP 8080 (idempotent restart)
$listeners = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
foreach ($c in $listeners) {
    try {
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
        Write-Host "Stopped PID $($c.OwningProcess) on port 8080."
    } catch {
        Write-Warning "Could not stop PID $($c.OwningProcess): $_"
    }
}

if (Test-Path $LogFile) {
    Remove-Item -Path $LogFile -Force -ErrorAction SilentlyContinue
}

$cmd = "cd /d `"$LobsterRoot`" && node server.cjs >> `"$LogFile`" 2>&1"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $cmd -WindowStyle Hidden

Write-Host "Started LobsterBoard (node server.cjs) in background; logging to $LogFile"
