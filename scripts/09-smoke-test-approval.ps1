#Requires -Version 5.1
# Thin wrapper: approval-path E2E smoke (pending approval, no auto-approve decision).
# Forwards arguments to 09-smoke-test-e2e.ps1 -ApprovalPath
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $here '09-smoke-test-e2e.ps1') -ApprovalPath @args
