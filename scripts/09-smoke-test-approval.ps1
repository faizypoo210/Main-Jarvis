#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $scriptDir '09-smoke-test-e2e.ps1'

if (-not (Test-Path -LiteralPath $target)) {
    throw "Missing target script: $target"
}

& $target -ApprovalPath @args
exit $LASTEXITCODE
