#Requires -Version 5.1
<#
.SYNOPSIS
  End-of-day release readiness + handoff snapshot (honest pass/fail/skip; not a giant release system).

.DESCRIPTION
  Runs read-only checks against the governed stack, optional Phase 8 aggregate, Command Center build,
  and writes a markdown report under docs/reports/.

  Pass: check succeeded.
  Fail: check ran and failed (non-zero exit, HTTP error, tsc/vite errors).
  Skip: prerequisite missing (e.g. node_modules, or -SkipPhase8 / -SkipCommandCenterBuild).

.PARAMETER SkipPhase8
  Do not run scripts/08-final-report.ps1 (marks Phase 8 block as skipped in the report).

.PARAMETER SkipCommandCenterBuild
  Do not run npm run build in services/command-center.
#>
param(
    [switch]$SkipPhase8,
    [switch]$SkipCommandCenterBuild
)

$ErrorActionPreference = 'Continue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$ReportsDir = Join-Path $RepoRoot 'docs\reports'
if (-not (Test-Path -LiteralPath $ReportsDir)) {
    New-Item -ItemType Directory -Path $ReportsDir -Force | Out-Null
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dayTag = Get-Date -Format 'yyyy-MM-dd'
$ReportPath = Join-Path $ReportsDir "day-wrap-$dayTag-$stamp.md"

function Invoke-ReportScript {
    param([string]$Path, [string]$Label)
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Path 2>&1 | Out-String
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = -1 }
    return @{ Label = $Label; Output = $out; ExitCode = $code }
}

function Get-CpHealthOk {
    try {
        $u = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_URL', 'User')
        if ([string]::IsNullOrWhiteSpace($u)) { $u = $env:CONTROL_PLANE_URL }
        if ([string]::IsNullOrWhiteSpace($u)) { $u = 'http://127.0.0.1:8001' }
        $b = $u.TrimEnd('/')
        $r = Invoke-WebRequest -Uri "$b/health" -UseBasicParsing -TimeoutSec 12
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Get-GitLine {
    param([Parameter(Mandatory = $true)][string[]]$GitArguments)
    Push-Location $RepoRoot
    try {
        $o = & git.exe @GitArguments 2>&1 | Out-String
        return $o.Trim()
    } catch {
        return '(git unavailable)'
    } finally {
        Pop-Location
    }
}

function Get-MigrationNote {
    $cp = Join-Path $RepoRoot 'services\control-plane'
    if (-not (Test-Path (Join-Path $cp 'alembic.ini'))) {
        return 'SKIP - alembic.ini not found'
    }
    Push-Location $cp
    try {
        $heads = & python -m alembic heads 2>&1 | Out-String
        $hCode = $LASTEXITCODE
        $cur = & python -m alembic current 2>&1 | Out-String
        $cCode = $LASTEXITCODE
        if ($hCode -ne 0 -or $cCode -ne 0) {
            $detail = "heads exit=$hCode : $($heads.Trim()) | current exit=$cCode : $($cur.Trim())"
            if ($detail.Length -gt 900) { $detail = $detail.Substring(0, 900) + '...' }
            return "SKIP - python -m alembic in services/control-plane failed (set DATABASE_URL, start Postgres, or run where DB is reachable). $detail"
        }
        $ht = $heads.Trim()
        $ct = $cur.Trim()
        $body = "alembic heads:`n$ht`n`nalembic current:`n$ct`n`nIf current is behind heads, apply migrations to the PostgreSQL instance used by the control plane."
        if ($body.Length -gt 2000) { $body = $body.Substring(0, 2000) + '...' }
        return $body
    } finally {
        Pop-Location
    }
}

# --- Collect git context ---
$branch = Get-GitLine -GitArguments @('rev-parse', '--abbrev-ref', 'HEAD')
$shortSha = Get-GitLine -GitArguments @('rev-parse', '--short', 'HEAD')
$fullSha = Get-GitLine -GitArguments @('rev-parse', 'HEAD')
$subject = Get-GitLine -GitArguments @('log', '-1', '--format=%s')
$todayLog = Get-GitLine -GitArguments @('log', '--since=midnight', '--format=- %h %s')

$healthOk = Get-CpHealthOk

$rows = New-Object System.Collections.ArrayList

function Add-Row([string]$Step, [string]$Status, [string]$Detail) {
    [void]$rows.Add([pscustomobject]@{ Step = $Step; Status = $Status; Detail = $Detail })
}

# --- Governed catalog + operator surfaces (require reachable /health) ---
$gPath = Join-Path $ScriptDir '19-smoke-governed-action-catalog.ps1'
$sPath = Join-Path $ScriptDir '19-smoke-operator-surfaces.ps1'
$g = @{ Output = '(not run - control plane unreachable)'; ExitCode = -1 }
$s = @{ Output = '(not run - control plane unreachable)'; ExitCode = -1 }
if (-not $healthOk) {
    Add-Row '19-smoke-governed-action-catalog' 'SKIP' 'Control plane /health not OK - start stack or set CONTROL_PLANE_URL'
    Add-Row '19-smoke-operator-surfaces' 'SKIP' 'Control plane /health not OK'
} else {
    $g = Invoke-ReportScript $gPath 'governed_catalog'
    $stg = if ($g.ExitCode -eq 0) { 'PASS' } else { 'FAIL' }
    Add-Row '19-smoke-governed-action-catalog' $stg ("exit $($g.ExitCode)")
    $s = Invoke-ReportScript $sPath 'operator_surfaces'
    $sts = if ($s.ExitCode -eq 0) { 'PASS' } else { 'FAIL' }
    Add-Row '19-smoke-operator-surfaces' $sts ("exit $($s.ExitCode)")
}

# --- Phase 8 aggregate ---
$p8Out = ''
$p8Code = -1
if ($SkipPhase8) {
    Add-Row '08-final-report.ps1 (Phase 8)' 'SKIP' '-SkipPhase8'
} else {
    $p8 = Invoke-ReportScript (Join-Path $ScriptDir '08-final-report.ps1') 'phase8'
    $p8Out = $p8.Output
    $p8Code = $p8.ExitCode
    $st = if ($p8.ExitCode -eq 0) { 'PASS' } else { 'FAIL' }
    Add-Row '08-final-report.ps1 (Phase 8)' $st ("exit $($p8.ExitCode); also docs/08-deployment-report.txt")
}

# --- Command Center build ---
$ccRoot = Join-Path $RepoRoot 'services\command-center'
$nm = Join-Path $ccRoot 'node_modules'
if ($SkipCommandCenterBuild) {
    Add-Row 'command-center npm run build' 'SKIP' '-SkipCommandCenterBuild'
} elseif (-not (Test-Path -LiteralPath $nm)) {
    Add-Row 'command-center npm run build' 'SKIP' 'node_modules missing - run npm install in services/command-center'
} else {
    $bc = -1
    Push-Location $ccRoot
    try {
        $buildOut = & npm run build 2>&1 | Out-String
        $bc = $LASTEXITCODE
        if ($null -eq $bc) { $bc = -1 }
        $st = if ($bc -eq 0) { 'PASS' } else { 'FAIL' }
        $snippet = if ($buildOut.Length -gt 1200) { $buildOut.Substring(0, 1200) + "`n…" } else { $buildOut }
        Add-Row 'command-center npm run build' $st ("exit $bc`n$snippet")
    } finally {
        Pop-Location
    }
}

# --- Workspace governance (low-diff; same as Phase 8 subset) ---
$wg = Invoke-ReportScript (Join-Path $ScriptDir '08-smoke-workspace-governance.ps1') 'workspace_gov'
$wgSt = if ($wg.ExitCode -eq 0) { 'PASS' } else { 'FAIL' }
Add-Row '08-smoke-workspace-governance.ps1' $wgSt ("exit $($wg.ExitCode)")

$migrationNote = Get-MigrationNote

# --- Counts ---
$passN = ($rows | Where-Object { $_.Status -eq 'PASS' }).Count
$failN = ($rows | Where-Object { $_.Status -eq 'FAIL' }).Count
$skipN = ($rows | Where-Object { $_.Status -eq 'SKIP' }).Count

$overall = if ($failN -gt 0) { 'FAIL' } elseif ($passN -gt 0) { 'PASS_WITH_SKIPS' } else { 'SKIP_ONLY' }

# --- Markdown ---
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("# Jarvis day-wrap snapshot ($dayTag)")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Meta')
[void]$sb.AppendLine('')
[void]$sb.AppendLine("| Field | Value |")
[void]$sb.AppendLine("|-------|-------|")
[void]$sb.AppendLine("| Git branch | ``$branch`` |")
[void]$sb.AppendLine("| Commit (short) | ``$shortSha`` |")
[void]$sb.AppendLine("| Commit (full) | ``$fullSha`` |")
[void]$sb.AppendLine("| HEAD subject | $subject |")
[void]$sb.AppendLine("| Control plane /health (default URL) | $(if ($healthOk) { 'reachable' } else { '**not reachable**' }) |")
[void]$sb.AppendLine("| Report file | ``docs/reports/$(Split-Path $ReportPath -Leaf)`` |")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Pass / fail / skip summary')
[void]$sb.AppendLine('')
[void]$sb.AppendLine("| Step | Status | Detail |")
[void]$sb.AppendLine("|------|--------|--------|")
foreach ($r in $rows) {
    $d = $r.Detail -replace "[\r\n]+", '; ' -replace '\|', '/'
    if ($d.Length -gt 500) { $d = $d.Substring(0, 500) + '...' }
    [void]$sb.AppendLine("| $($r.Step) | $($r.Status) | $d |")
}
[void]$sb.AppendLine('')
[void]$sb.AppendLine("Totals: **$passN** pass, **$failN** fail, **$skipN** skip. Overall: **$overall**.")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Implemented surfaces exercised (this run)')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('- **Governed action catalog** - `GET /api/v1/operator/action-catalog` + six `approval_action_type` rows.')
[void]$sb.AppendLine('- **Operator inbox** - `GET /api/v1/operator/inbox`.')
[void]$sb.AppendLine('- **Workers registry (read)** - `GET /api/v1/operator/workers`.')
[void]$sb.AppendLine('- **Cost** - `GET /api/v1/operator/cost-guardrails`, `GET /api/v1/operator/cost-events`.')
[void]$sb.AppendLine('- **Phase 8 aggregate** - infrastructure, gateway, LAN, operator bundle from `08-smoke-operator-control-plane.ps1`, workspace governance (unless skipped).')
[void]$sb.AppendLine('- **Command Center** - `npm run build` (TypeScript + Vite) when `node_modules` exists (unless skipped).')
[void]$sb.AppendLine('- **Workspace governance smoke** - manifest audit via `08-smoke-workspace-governance.ps1`.')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('**Not in this snapshot:** live E2E (`09-smoke-test-e2e.ps1`), coordinator/executor chain, voice/SMS/Twilio, OAuth flows - verify separately when those runtimes are up.')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Migrations / database')
[void]$sb.AppendLine('')
[void]$sb.AppendLine($migrationNote)
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Manual / environment dependencies')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('- **Docker:** Postgres `jarvis-postgres`, Redis `jarvis-redis` for canonical local stack.')
[void]$sb.AppendLine('- **Control plane:** `CONTROL_PLANE_URL`, `CONTROL_PLANE_API_KEY` (for mutating routes, SSE in Phase 8 smoke, E2E).')
[void]$sb.AppendLine('- **OpenClaw:** gateway on 18789, machine-local `openclaw.json` / auth profiles - not in repo.')
[void]$sb.AppendLine('- **GitHub / Gmail governed workflows:** `JARVIS_GITHUB_TOKEN`, `JARVIS_GMAIL_*` - external probes in `08-smoke-external-probes.ps1` skip when absent.')
[void]$sb.AppendLine('- **SMS approvals:** Twilio + `JARVIS_SMS_APPROVALS_ENABLED` per `docs/SMS_APPROVALS.md`.')
[void]$sb.AppendLine('- **Voice:** Whisper/GPU, `.env` beside `voice/server.py`, same API key as control plane for triage/catalog.')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## What landed today (git, since local midnight)')
[void]$sb.AppendLine('')
if ([string]::IsNullOrWhiteSpace($todayLog)) {
    [void]$sb.AppendLine('_(no commits since midnight on this machine)_')
} else {
    [void]$sb.AppendLine($todayLog)
}
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Resume tomorrow')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('### Current state')
[void]$sb.AppendLine("- Branch ``$branch`` @ ``$shortSha``: $subject")
[void]$sb.AppendLine("- Control plane probe: $(if ($healthOk) { 'last check reached `/health`.' } else { '**`/health` was not reachable** - bring up the stack before deep verification.' })")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('### What remains manual or out-of-band')
[void]$sb.AppendLine('- Provider credentials, gateway model selection, and live OpenClaw workspace under `%USERPROFILE%\\.openclaw\\`.')
[void]$sb.AppendLine('- Full mission pipeline proof: `09-smoke-test-e2e.ps1` or `14-rehearse-live-stack.ps1` when coordinator + executor + gateway are running.')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('### Next best logical step')
if ($failN -gt 0) {
    [void]$sb.AppendLine('1. Fix failing rows in **Pass / fail / skip summary** (often: start Docker services + control plane + gateway, then re-run).')
    [void]$sb.AppendLine('2. When core is green, run `09-smoke-test-e2e.ps1` for end-to-end governed command path.')
} else {
    [void]$sb.AppendLine('1. If anything was **SKIP** (no `node_modules`, `-SkipPhase8`, etc.), run the skipped steps when ready.')
    [void]$sb.AppendLine('2. Run live E2E or golden-path rehearsal when validating execution - not required for this handoff file.')
}
[void]$sb.AppendLine('')
[void]$sb.AppendLine('---')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Raw excerpts (debug)')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('### 19-smoke-governed-action-catalog')
[void]$sb.AppendLine('```')
[void]$sb.AppendLine(($g.Output.Trim()))
[void]$sb.AppendLine('```')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('### 19-smoke-operator-surfaces')
[void]$sb.AppendLine('```')
[void]$sb.AppendLine(($s.Output.Trim()))
[void]$sb.AppendLine('```')
if (-not $SkipPhase8) {
    [void]$sb.AppendLine('')
    [void]$sb.AppendLine('### 08-final-report (truncated)')
    [void]$sb.AppendLine('```')
    $p8trim = $p8Out
    if ($p8trim.Length -gt 4000) { $p8trim = $p8trim.Substring(0, 4000) + "`n…" }
    [void]$sb.AppendLine($p8trim.Trim())
    [void]$sb.AppendLine('```')
}

Set-Content -Path $ReportPath -Value $sb.ToString() -Encoding UTF8

Write-Host $sb.ToString()
Write-Host ""
Write-Host "Wrote $ReportPath" -ForegroundColor Green

# Exit: 0 if no FAIL rows; 1 if any FAIL (skips do not force failure)
if ($failN -gt 0) {
    Write-Host "Day-wrap completed with failures ($failN). See report." -ForegroundColor Yellow
    exit 1
}
Write-Host "Day-wrap completed (pass=$passN skip=$skipN)." -ForegroundColor Green
exit 0
