<#
.SYNOPSIS
  Stops any listener on port 18789, then starts `openclaw gateway run --force` in the background with logs at %USERPROFILE%\.openclaw\gateway.log (idempotent).
#>
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Step "=== JARVIS Phase 3: Start OpenClaw Gateway ==="

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
    Write-Fail "openclaw not found. Run .\scripts\03-install-openclaw.ps1 first."
    exit 1
}

$base = Join-Path $env:USERPROFILE ".openclaw"
$log = Join-Path $base "gateway.log"
if (-not (Test-Path -LiteralPath $base)) {
    New-Item -ItemType Directory -Path $base -Force | Out-Null
}

# Load User-scoped env (ANTHROPIC_API_KEY) into this session
$k = [Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
if (-not [string]::IsNullOrEmpty($k)) { $env:ANTHROPIC_API_KEY = $k }

Write-Step "Stopping processes listening on port 18789 (if any)..."
$prevEa = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try {
    $conns = Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $owningPid = $c.OwningProcess
        if ($owningPid) {
            Write-Host "Stopping PID $owningPid on port 18789"
            Stop-Process -Id $owningPid -Force -ErrorAction SilentlyContinue
        }
    }
} finally {
    $ErrorActionPreference = $prevEa
}

Start-Sleep -Seconds 1

$oc = (Get-Command openclaw).Source
Write-Step "Starting gateway detached (log: $log) ..."

$anth = [Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
if (-not [string]::IsNullOrEmpty($anth)) { $env:ANTHROPIC_API_KEY = $anth }

# Start-Process + hidden PowerShell: npm's openclaw.ps1 shim needs a real shell; Start-Job often misses PATH.
$inner = "& `"$oc`" gateway run --force --port 18789 *>> `"$log`""
$p = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-WindowStyle", "Hidden", "-Command", $inner) -WindowStyle Hidden -PassThru

Write-Ok "Launched gateway via Start-Process (PID $($p.Id)); output appended to $log"
Write-Host "Wait a few seconds, then run .\scripts\03-verify-openclaw.ps1" -ForegroundColor DarkGray
exit 0
