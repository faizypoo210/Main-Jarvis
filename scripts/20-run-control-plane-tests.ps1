# Run control-plane pytest suite (requires PostgreSQL — see docs/TESTING.md).
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $repoRoot "services\control-plane")
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v $args
