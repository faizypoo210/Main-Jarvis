#Requires -Version 5.1
<#
.SYNOPSIS
  Single entrypoint to verify the operator eval/harness layer (semantics -> golden path -> optional benchmark).

.DESCRIPTION
  Explicit operator command - not used by startup or boot.
  1) scripts/16-verify-harness-semantics.ps1  (fast, no control plane / no missions)
  2) scripts/13-rehearse-golden-path.ps1       (synthetic API rehearsal; creates mission rows)
  3) scripts/15-benchmark-operator-loop.ps1    (optional; synthetic-only unless you add flags yourself)

  Exits 0 only when all required steps succeed. Final line distinguishes harness vs preconditions vs API contract drift. Summary includes classification_source (semantics|synthetic|benchmark|none).

.PARAMETER SkipBenchmark
  Do not run 15-benchmark-operator-loop.ps1 (synthetic-only benchmark with JSON report).

.PARAMETER BenchmarkOutputDir
  Passed to 15 as -OutputDir (default inside 15 is repo docs/reports).

.PARAMETER BenchmarkSkipSseProbe
  Passed to 15 as -SkipSseProbe (faster; no curl SSE timing).

.PARAMETER SkipRedisIsolationVerify
  Passed to 13 (skip Redis XLEN before/after compare).

.PARAMETER ControlPlaneUrl
  Passed to 13 and 15 when set.
#>
param(
    [switch]$SkipBenchmark,
    [string]$BenchmarkOutputDir = "",
    [switch]$BenchmarkSkipSseProbe,
    [switch]$SkipRedisIsolationVerify,
    [string]$ControlPlaneUrl = ""
)

$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path $ScriptDir -Parent

function Get-PwshExe {
    $p = (Get-Command powershell.exe -ErrorAction SilentlyContinue).Source
    if ($p) { return $p }
    $p = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if ($p) { return $p }
    throw 'powershell.exe or pwsh.exe not found.'
}

function Invoke-OperatorChildScript {
    param(
        [string]$RelativePath,
        [string[]]$ExtraArgs = @()
    )
    $full = Join-Path $ScriptDir $RelativePath
    if (-not (Test-Path -LiteralPath $full)) {
        throw "Missing script: $full"
    }
    $shell = Get-PwshExe
    $argList = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $full
    ) + $ExtraArgs
    $p = Start-Process -FilePath $shell -ArgumentList $argList -WorkingDirectory $RepoRoot `
        -Wait -PassThru -NoNewWindow
    return $p.ExitCode
}

function Invoke-OperatorChildScriptWithOutput {
    param(
        [string]$RelativePath,
        [string[]]$ExtraArgs = @()
    )
    $full = Join-Path $ScriptDir $RelativePath
    if (-not (Test-Path -LiteralPath $full)) {
        throw "Missing script: $full"
    }
    $shell = Get-PwshExe
    $stdOut = Join-Path $env:TEMP ("jarvis-17-{0}.stdout.txt" -f [guid]::NewGuid())
    $stdErr = Join-Path $env:TEMP ("jarvis-17-{0}.stderr.txt" -f [guid]::NewGuid())
    try {
        $argList = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $full
        ) + $ExtraArgs
        $p = Start-Process -FilePath $shell -ArgumentList $argList -WorkingDirectory $RepoRoot `
            -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdOut -RedirectStandardError $stdErr
        $outText = ''
        if (Test-Path -LiteralPath $stdOut) {
            $outText = Get-Content -LiteralPath $stdOut -Raw
            if ($null -eq $outText) { $outText = '' }
        }
        return @{ ExitCode = $p.ExitCode; StdOut = $outText }
    }
    finally {
        Remove-Item -LiteralPath $stdOut -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stdErr -ErrorAction SilentlyContinue
    }
}

function Get-SyntheticClassFromStdout {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return 'precondition_fail' }
    if ($Text -match 'GOLDEN_PATH_SYNTHETIC_CLASS=(\S+)') { return $Matches[1].Trim() }
    return 'precondition_fail'
}

Write-Host ""
Write-Host "Operator eval verification (harness layer)" -ForegroundColor White
Write-Host "Repo: $RepoRoot" -ForegroundColor DarkGray

# --- Step 1: semantics (no runtime) ---
Write-Host ""
Write-Host "[1/3] Harness semantics (16)..." -ForegroundColor Cyan
$code16 = Invoke-OperatorChildScript -RelativePath '16-verify-harness-semantics.ps1'
$semanticsOk = ($code16 -eq 0)
if (-not $semanticsOk) {
    Write-Host "  -> FAIL (exit $code16)" -ForegroundColor Red
}
else {
    Write-Host "  -> OK" -ForegroundColor Green
}

# --- Step 2: synthetic golden path ---
Write-Host ""
Write-Host "[2/3] Synthetic golden path (13)..." -ForegroundColor Cyan
$syntheticOk = $false
$syntheticFailureClass = 'skipped'
$stdout13 = ''
if (-not $semanticsOk) {
    Write-Host "  -> skipped (harness semantics failed)" -ForegroundColor DarkGray
}
else {
    $args13 = @()
    if ($SkipRedisIsolationVerify) { $args13 += '-SkipRedisIsolationVerify' }
    if (-not [string]::IsNullOrWhiteSpace($ControlPlaneUrl)) {
        $args13 += '-ControlPlaneUrl', $ControlPlaneUrl
    }
    $r13 = Invoke-OperatorChildScriptWithOutput -RelativePath '13-rehearse-golden-path.ps1' -ExtraArgs $args13
    $stdout13 = $r13.StdOut
    $syntheticOk = ($r13.ExitCode -eq 0)
    if ($syntheticOk) {
        $syntheticFailureClass = 'pass'
        Write-Host "  -> OK" -ForegroundColor Green
    }
    else {
        $syntheticFailureClass = Get-SyntheticClassFromStdout -Text $stdout13
        if ($syntheticFailureClass -eq 'pass') { $syntheticFailureClass = 'precondition_fail' }
        Write-Host "  -> FAIL (exit $($r13.ExitCode); class=$syntheticFailureClass)" -ForegroundColor Red
    }
}

# --- Step 3: benchmark (synthetic-only; no -IncludeLiveStack) ---
$benchmarkOk = $null
$benchmarkLabel = 'skipped'
if (-not $SkipBenchmark) {
    if (-not $semanticsOk -or -not $syntheticOk) {
        Write-Host ""
        Write-Host "[3/3] Operator benchmark skipped (prior step failed)" -ForegroundColor DarkGray
        $benchmarkLabel = 'skipped'
    }
    else {
        Write-Host ""
        Write-Host "[3/3] Operator benchmark (15, synthetic-only)..." -ForegroundColor Cyan
        $args15 = @()
        if (-not [string]::IsNullOrWhiteSpace($ControlPlaneUrl)) {
            $args15 += '-ControlPlaneUrl', $ControlPlaneUrl
        }
        if (-not [string]::IsNullOrWhiteSpace($BenchmarkOutputDir)) {
            $args15 += '-OutputDir', $BenchmarkOutputDir
        }
        if ($BenchmarkSkipSseProbe) {
            $args15 += '-SkipSseProbe'
        }
        $code15 = Invoke-OperatorChildScript -RelativePath '15-benchmark-operator-loop.ps1' -ExtraArgs $args15
        $benchmarkOk = ($code15 -eq 0)
        $benchmarkLabel = if ($benchmarkOk) { 'true' } else { 'false' }
        if (-not $benchmarkOk) {
            Write-Host "  -> FAIL (exit $code15)" -ForegroundColor Red
        }
        else {
            Write-Host "  -> OK" -ForegroundColor Green
        }
    }
}
else {
    Write-Host ""
    Write-Host "[3/3] Operator benchmark skipped (-SkipBenchmark)" -ForegroundColor DarkGray
}

$overallOk = $semanticsOk -and $syntheticOk -and ($SkipBenchmark -or ($benchmarkOk -eq $true))

$overallClassification = 'pass'
if (-not $semanticsOk) {
    $overallClassification = 'harness_fail'
}
elseif (-not $syntheticOk) {
    $overallClassification = $syntheticFailureClass
    if ($overallClassification -eq 'pass') { $overallClassification = 'precondition_fail' }
}
elseif (-not $SkipBenchmark -and ($benchmarkOk -ne $true)) {
    $overallClassification = 'precondition_fail'
}

$classificationSource = 'none'
if (-not $overallOk) {
    if (-not $semanticsOk) {
        $classificationSource = 'semantics'
    }
    elseif (-not $syntheticOk) {
        $classificationSource = 'synthetic'
    }
    elseif (-not $SkipBenchmark -and ($benchmarkOk -ne $true)) {
        $classificationSource = 'benchmark'
    }
}

Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host ("  semantics_ok:              {0}" -f $(if ($semanticsOk) { 'true' } else { 'false' }))
Write-Host ("  synthetic_ok:              {0}" -f $(if ($syntheticOk) { 'true' } else { 'false' }))
Write-Host ("  synthetic_failure_class:   {0}" -f $syntheticFailureClass)
if ($SkipBenchmark) {
    Write-Host "  benchmark_ok:              skipped"
}
else {
    Write-Host ("  benchmark_ok:              {0}" -f $benchmarkLabel)
}
Write-Host ("  overall_classification:    {0}" -f $overallClassification)
Write-Host ("  classification_source:       {0}" -f $classificationSource)
Write-Host ("  overall_ok:                {0}" -f $(if ($overallOk) { 'true' } else { 'false' }))
Write-Host "----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

if ($overallOk) {
    Write-Host "Operator eval verification: PASS" -ForegroundColor Green
    exit 0
}
if ($overallClassification -eq 'harness_fail') {
    Write-Host "Operator eval verification: FAIL (harness)" -ForegroundColor Red
    exit 1
}
if ($overallClassification -eq 'contract_drift') {
    Write-Host "Operator eval verification: FAIL (contract drift)" -ForegroundColor Red
    exit 1
}
Write-Host "Operator eval verification: FAIL (preconditions)" -ForegroundColor Yellow
exit 1
