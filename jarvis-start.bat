@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo === Jarvis start ===
echo Repo: %CD%
echo.

echo === Docker (wait up to 60s for docker info) ===
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='SilentlyContinue'; " ^
  "$null = docker info 2>&1; " ^
  "if ($LASTEXITCODE -ne 0) { " ^
  "  $candidates = @('C:\Program Files\Docker\Docker\Docker Desktop.exe','C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe'); " ^
  "  $dockerExe = $null; foreach ($c in $candidates) { if (Test-Path -LiteralPath $c) { $dockerExe = $c; break } }; " ^
  "  if (-not $dockerExe) { Write-Host 'ERROR: Docker Desktop not found under Program Files or Program Files (x86).' -ForegroundColor Red; exit 2 }; " ^
  "  Start-Process -FilePath $dockerExe | Out-Null; " ^
  "  $deadline = (Get-Date).AddSeconds(60); " ^
  "  while ((Get-Date) -lt $deadline) { " ^
  "    $null = docker info 2>&1; " ^
  "    if ($LASTEXITCODE -eq 0) { exit 0 } " ^
  "    Start-Sleep -Seconds 2 " ^
  "  }; " ^
  "  exit 1 " ^
  "} else { exit 0 }"
if errorlevel 2 (
  echo Docker Desktop executable was not found in the checked paths.
  pause
  exit /b 2
)
if errorlevel 1 (
  echo Docker did not become ready within 60 seconds.
  pause
  exit /b 1
)

echo === docker compose up -d ===
docker compose up -d
if errorlevel 1 (
  echo docker compose up -d failed.
  pause
  exit /b 1
)

echo === Waiting for Postgres (pg_isready, up to 10 x 3s) ===
set PG_OK=0
for /l %%i in (1,1,10) do (
  docker exec jarvis-postgres pg_isready -U jarvis
  if !errorlevel! equ 0 (
    set PG_OK=1
    goto PG_DONE
  )
  echo Attempt %%i/10: not ready, waiting 3 seconds...
  timeout /t 3 /nobreak >nul
)
:PG_DONE
if !PG_OK! neq 1 (
  echo Postgres did not become ready in time.
  pause
  exit /b 1
)
echo Postgres is ready.
echo.

echo === Alembic (services\control-plane) ===
pushd "%~dp0services\control-plane"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m alembic upgrade head
) else (
  python -m alembic upgrade head
)
set ALE=!errorlevel!
popd
if !ALE! neq 0 (
  echo Alembic upgrade head failed.
  pause
  exit /b 1
)
echo.

echo === jarvis.ps1 ===
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0jarvis.ps1"
if errorlevel 1 (
  echo jarvis.ps1 exited with a non-zero code.
  pause
  exit /b 1
)

echo.
echo Jarvis start sequence finished.
pause
endlocal
exit /b 0
