# Fast control-plane tests (pytest -m unit) — no Postgres migrations required.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $repoRoot "services\control-plane")
python -m pip install -q -r requirements.txt -r requirements-dev.txt
python -m pytest -m unit -q $args
