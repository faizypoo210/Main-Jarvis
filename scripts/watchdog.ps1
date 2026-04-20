#Requires -Version 5.1
# Long-running supervisor: control plane + voice (HTTP), executor + coordinator (host PID).
# Started by jarvis.ps1 after bring-up. Logs to .jarvis-local/watchdog.log
param(
    [string]$JarvisRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($JarvisRoot)) {
    $JarvisRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$PollSeconds = 15
$BackoffSeconds = 3
$RestartCooldownSeconds = 30
$MaxConsecutiveErrors = 5
$logDir = Join-Path $JarvisRoot '.jarvis-local'
$logPath = Join-Path $logDir 'watchdog.log'
$lockPath = Join-Path $logDir 'watchdog.lock'

function Ensure-LogDir {
    if (-not (Test-Path -LiteralPath $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
}

function Write-WatchdogLog {
    param([Parameter(Mandatory)][string]$Message)
    Ensure-LogDir
    $ts = (Get-Date).ToUniversalTime().ToString('o')
    "${ts} ${Message}" | Add-Content -LiteralPath $logPath -Encoding UTF8
}

function Get-LaunchStatePid {
    param(
        [Parameter(Mandatory)][string]$ServiceName
    )
    $path = Join-Path $JarvisRoot '.jarvis-local\launch-state.json'
    if (-not (Test-Path -LiteralPath $path)) { return 0 }
    try {
        $raw = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        $j = $raw | ConvertFrom-Json
        foreach ($l in @($j.launches)) {
            if ([string]$l.name -eq $ServiceName) {
                return [int]$l.pid
            }
        }
    } catch {
        return 0
    }
    return 0
}

function Test-ControlPlaneHealthy {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8001/health' -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Test-VoiceHealthy {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Test-HostPidAlive {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    try {
        $null = Get-Process -Id $ProcessId -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Test-RestartCooldown {
    param(
        [Parameter(Mandatory)][string]$Role,
        [Parameter(Mandatory)][hashtable]$LastRestartTable
    )
    if (-not $LastRestartTable.ContainsKey($Role)) { return $false }
    $elapsed = (Get-Date) - $LastRestartTable[$Role]
    return ($elapsed.TotalSeconds -lt $RestartCooldownSeconds)
}

function Stop-HttpServiceHostProcess {
    param(
        [Parameter(Mandatory)][string]$Role,
        [int]$TrackedHostPid
    )
    $filePid = Get-LaunchStatePid -ServiceName $Role
    $pids = @()
    if ($filePid -gt 0) { $pids += $filePid }
    if ($TrackedHostPid -gt 0 -and $TrackedHostPid -ne $filePid) { $pids += $TrackedHostPid }
    foreach ($procId in ($pids | Sort-Object -Unique)) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    if ($pids.Count -gt 0) {
        Start-Sleep -Seconds 2
    }
}

function Start-WatchdogServiceHost {
    param(
        [Parameter(Mandatory)][string]$Command,
        [System.Diagnostics.ProcessWindowStyle]$WindowStyle = 'Hidden'
    )
    try {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-Command', $Command
        ) -WindowStyle $WindowStyle -PassThru
        Start-Sleep -Milliseconds 600
        if ($null -eq $p) {
            return @{ Ok = $false; Pid = 0 }
        }
        $alive = Test-HostPidAlive -ProcessId $p.Id
        if (-not $alive) { return @{ Ok = $false; Pid = 0 } }
        return @{ Ok = $true; Pid = $p.Id }
    } catch {
        return @{ Ok = $false; Pid = 0 }
    }
}

$controlPlaneDir = Join-Path $JarvisRoot 'services\control-plane'
$coordDir = Join-Path $JarvisRoot 'coordinator'
$executorDir = Join-Path $JarvisRoot 'executor'

$cpCmd = "cd `"$controlPlaneDir`"; `$env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001"
$voiceCmd = "cd `"$JarvisRoot`"; .\voice\.venv\Scripts\python.exe -m uvicorn voice.server:app --host 0.0.0.0 --port 8000"
$coordCmd = "cd `"$coordDir`"; .\.venv\Scripts\python.exe coordinator.py"
$execCmd = "cd `"$executorDir`"; .\.venv\Scripts\python.exe -u worker.py"

Ensure-LogDir

if (Test-Path -LiteralPath $lockPath) {
    $lockPid = 0
    try {
        $rawLock = (Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8).Trim()
        if ($rawLock) { $lockPid = [int]$rawLock }
    } catch {
        $lockPid = 0
    }
    if ($lockPid -gt 0) {
        $lockProc = Get-Process -Id $lockPid -ErrorAction SilentlyContinue
        if ($null -ne $lockProc) {
            Write-WatchdogLog 'watchdog already running, exiting'
            exit 0
        }
    }
    Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
}

$watchdogOwnPid = $PID
[System.IO.File]::WriteAllText($lockPath, "$watchdogOwnPid")

$LastRestart = @{}

[int]$script:ControlPlaneHostPid = Get-LaunchStatePid -ServiceName 'control-plane'
[int]$script:VoiceHostPid = Get-LaunchStatePid -ServiceName 'voice'
[int]$script:ExecutorHostPid = Get-LaunchStatePid -ServiceName 'executor'
[int]$script:CoordinatorHostPid = Get-LaunchStatePid -ServiceName 'coordinator'

Write-WatchdogLog ("watchdog start jarvisRoot={0} poll={1}s cooldown={2}s own_pid={3} cp_host_pid={4} voice_host_pid={5} executor_host_pid={6} coordinator_host_pid={7}" -f `
        $JarvisRoot, $PollSeconds, $RestartCooldownSeconds, $watchdogOwnPid, $script:ControlPlaneHostPid, $script:VoiceHostPid, $script:ExecutorHostPid, $script:CoordinatorHostPid)

try {
    $ConsecutiveErrors = 0
    while ($true) {
        try {
            $failed = @()
            if (-not (Test-ControlPlaneHealthy)) { $failed += 'control-plane' }
            if (-not (Test-VoiceHealthy)) { $failed += 'voice' }
            if (-not (Test-HostPidAlive -ProcessId $script:ExecutorHostPid)) { $failed += 'executor' }
            if (-not (Test-HostPidAlive -ProcessId $script:CoordinatorHostPid)) { $failed += 'coordinator' }

            if ($failed.Count -eq 0) {
                Start-Sleep -Seconds $PollSeconds
                $ConsecutiveErrors = 0
                continue
            }

            $detail = @(
                $(if ($failed -contains 'control-plane') { 'control_plane_GET_health_not_200' }),
                $(if ($failed -contains 'voice') { 'voice_GET_slash_not_200' }),
                $(if ($failed -contains 'executor') { "executor_host_pid=$script:ExecutorHostPid" }),
                $(if ($failed -contains 'coordinator') { "coordinator_host_pid=$script:CoordinatorHostPid" })
            ) | Where-Object { $_ }

            $toRestart = @()
            foreach ($role in $failed) {
                if (Test-RestartCooldown -Role $role -LastRestartTable $LastRestart) {
                    Write-WatchdogLog ("skip_restart service={0} reason=cooldown" -f $role)
                    continue
                }
                $toRestart += $role
            }

            if ($toRestart.Count -eq 0) {
                Write-WatchdogLog ("failure services={0} detail={1} restart_skipped reason=all_cooldown" -f (($failed -join ',')), (($detail -join ';')))
                Start-Sleep -Seconds $PollSeconds
                $ConsecutiveErrors = 0
                continue
            }

            Write-WatchdogLog ("failure services={0} detail={1}" -f (($failed -join ',')), (($detail -join ';')))

            Start-Sleep -Seconds $BackoffSeconds

            if ($toRestart -contains 'control-plane') {
                Stop-HttpServiceHostProcess -Role 'control-plane' -TrackedHostPid $script:ControlPlaneHostPid
                $r = Start-WatchdogServiceHost -Command $cpCmd
                $script:ControlPlaneHostPid = if ($r.Pid) { [int]$r.Pid } else { 0 }
                $LastRestart['control-plane'] = Get-Date
                Write-WatchdogLog ("RESTART control-plane ok={0} new_host_pid={1} (http /health not 200)" -f $r.Ok, $script:ControlPlaneHostPid)
            }
            if ($toRestart -contains 'voice') {
                Stop-HttpServiceHostProcess -Role 'voice' -TrackedHostPid $script:VoiceHostPid
                $r = Start-WatchdogServiceHost -Command $voiceCmd
                $script:VoiceHostPid = if ($r.Pid) { [int]$r.Pid } else { 0 }
                $LastRestart['voice'] = Get-Date
                Write-WatchdogLog ("RESTART voice ok={0} new_host_pid={1} (http GET / not 200)" -f $r.Ok, $script:VoiceHostPid)
            }
            if ($toRestart -contains 'coordinator') {
                $r = Start-WatchdogServiceHost -Command $coordCmd
                $script:CoordinatorHostPid = if ($r.Pid) { [int]$r.Pid } else { 0 }
                $LastRestart['coordinator'] = Get-Date
                Write-WatchdogLog ("RESTART coordinator ok={0} new_host_pid={1} (tracked host gone)" -f $r.Ok, $script:CoordinatorHostPid)
            }
            if ($toRestart -contains 'executor') {
                $r = Start-WatchdogServiceHost -Command $execCmd
                $script:ExecutorHostPid = if ($r.Pid) { [int]$r.Pid } else { 0 }
                $LastRestart['executor'] = Get-Date
                Write-WatchdogLog ("RESTART executor ok={0} new_host_pid={1} (tracked host gone)" -f $r.Ok, $script:ExecutorHostPid)
            }

            Start-Sleep -Seconds $PollSeconds
            $ConsecutiveErrors = 0
        } catch {
            $ConsecutiveErrors++
            Write-WatchdogLog ("poll_loop_exception detail={0}" -f $_.Exception.Message)
            if ($ConsecutiveErrors -ge $MaxConsecutiveErrors) {
                Write-WatchdogLog ("poll_loop_fatal consecutive_errors={0} exiting" -f $MaxConsecutiveErrors)
                Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
                exit 1
            }
            Start-Sleep -Seconds $PollSeconds
        }
    }
} finally {
    Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
}
