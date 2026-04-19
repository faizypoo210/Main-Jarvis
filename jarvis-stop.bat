@echo off
setlocal
cd /d "%~dp0"

echo === Jarvis stop ===
echo Repo: %CD%
echo.

echo === Stop watchdog, service hosts, ports, and Jarvis-related children ===
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='SilentlyContinue'; " ^
  "$root = (Get-Location).Path; " ^
  "$lock = Join-Path $root '.jarvis-local\watchdog.lock'; " ^
  "if (Test-Path -LiteralPath $lock) { " ^
  "  $wdPid = 0; " ^
  "  try { $raw = (Get-Content -LiteralPath $lock -Raw).Trim(); if ($raw) { $wdPid = [int]$raw } } catch { $wdPid = 0 }; " ^
  "  if ($wdPid -gt 0) { Stop-Process -Id $wdPid -Force -ErrorAction SilentlyContinue }; " ^
  "}; " ^
  "$state = Join-Path $root '.jarvis-local\launch-state.json'; " ^
  "if (Test-Path -LiteralPath $state) { " ^
  "  try { " ^
  "    $j = Get-Content -LiteralPath $state -Raw -Encoding UTF8 | ConvertFrom-Json; " ^
  "    foreach ($l in @($j.launches)) { " ^
  "      $p = 0; try { $p = [int]$l.pid } catch { $p = 0 }; " ^
  "      if ($p -gt 0) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } " ^
  "    } " ^
  "  } catch { } " ^
  "}; " ^
  "foreach ($port in 8001,8000,5173) { Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }; " ^
  "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|uvicorn|node' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo === docker compose stop ===
docker compose stop
if errorlevel 1 (
  echo Note: docker compose stop returned a non-zero exit code.
)

if exist "%~dp0.jarvis-local\watchdog.lock" (
  del /f /q "%~dp0.jarvis-local\watchdog.lock"
  echo Removed .jarvis-local\watchdog.lock
)

echo.
echo Jarvis stop sequence finished.
endlocal
exit /b 0
