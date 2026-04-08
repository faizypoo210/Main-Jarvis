#Requires -Version 5.1
# Phase 8: Run all Phase 8 test scripts and write docs/08-deployment-report.txt; exits 0 if core suites pass.
$ErrorActionPreference = 'Continue'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$DocsDir = Join-Path $RepoRoot 'docs'
if (-not (Test-Path -LiteralPath $DocsDir)) {
    New-Item -ItemType Directory -Path $DocsDir -Force | Out-Null
}
$ReportPath = Join-Path $DocsDir '08-deployment-report.txt'

function Invoke-TestScript {
    param([string]$Path)
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Path 2>&1 | Out-String
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = -1 }
    return @{ Output = $out; ExitCode = $code }
}

function Get-Phase8Metric {
    param([string]$Text, [string]$Name)
    if ($Text -match "PHASE8 $Name (\d+) (\d+)") {
        return "$($matches[1])/$($matches[2])"
    }
    return '?/?'
}

$sInfra = Join-Path $ScriptDir '08-test-infrastructure.ps1'
$sGw = Join-Path $ScriptDir '08-test-gateway.ps1'
$sMc = Join-Path $ScriptDir '08-test-mission-control.ps1'
$sLan = Join-Path $ScriptDir '08-test-lan-access.ps1'
$sFlow = Join-Path $ScriptDir '08-test-full-flow.ps1'

$rInfra = Invoke-TestScript $sInfra
$rGw = Invoke-TestScript $sGw
$rMc = Invoke-TestScript $sMc
$rLan = Invoke-TestScript $sLan
$rFlow = Invoke-TestScript $sFlow

$mInfra = Get-Phase8Metric $rInfra.Output 'infrastructure'
$mGw = Get-Phase8Metric $rGw.Output 'gateway'
$mMc = Get-Phase8Metric $rMc.Output 'missioncontrol'
$mLan = Get-Phase8Metric $rLan.Output 'lan'
$mFlow = Get-Phase8Metric $rFlow.Output 'fullflow'

$corePass = ($rInfra.ExitCode -eq 0) -and ($rGw.ExitCode -eq 0) -and ($rLan.ExitCode -eq 0)
$overall = if ($corePass) { 'PASS' } else { 'FAIL' }

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('JARVIS Deployment Report')
[void]$sb.AppendLine('========================')
[void]$sb.AppendLine("Infrastructure:     $mInfra passed")
[void]$sb.AppendLine("Gateway + Agent:    $mGw passed")
[void]$sb.AppendLine("Mission Control:    $mMc passed")
[void]$sb.AppendLine("LAN Access:         $mLan passed")
[void]$sb.AppendLine("Full Flow:          $mFlow passed")
[void]$sb.AppendLine('========================')
[void]$sb.AppendLine("Overall: $overall")

Set-Content -Path $ReportPath -Value $sb.ToString() -Encoding UTF8

Write-Host $sb.ToString()

if (-not $corePass) {
    Write-Host "Core checks failed (infrastructure, gateway, or LAN)." -ForegroundColor Red
    exit 1
}
Write-Host "Phase 8 core checks passed." -ForegroundColor Green
exit 0
