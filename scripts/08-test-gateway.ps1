#Requires -Version 5.1
# Phase 8: OpenClaw gateway and config checks (read-only); exits 0 only if all 6 pass.
# Optional: set JARVIS_OPENCLAW_EXPECTED_MODEL to require an exact default-agent model string (e.g. after you configure MiniMax in openclaw.json).
$ErrorActionPreference = 'Continue'

Add-Type -AssemblyName System.Web.Extensions

$pass = 0
$fail = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Probe)
    try {
        $ok = & $Probe
        if ($ok) {
            Write-Host "[PASS] $Name"
            $script:pass++
        } else {
            Write-Host "[FAIL] $Name"
            $script:fail++
        }
    } catch {
        Write-Host "[FAIL] $Name - $($_.Exception.Message)"
        $script:fail++
    }
}

function Read-OpenClawJson {
    $path = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $raw = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $ser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $ser.MaxJsonLength = 67108864
    return $ser.DeserializeObject($raw)
}

Write-Host "=== 08-test-gateway (read-only) ===" -ForegroundColor Cyan

Test-Step 'openclaw status (gateway healthy)' {
    $out = & openclaw status 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { return $false }
    return ($out -match '(?i)healthy|ok|running|online|gateway')
}

Test-Step 'agent echo JARVIS_ONLINE' {
    $out = & openclaw agent --agent main --message 'Respond with exactly: JARVIS_ONLINE' 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { return $false }
    return ($out -match 'JARVIS_ONLINE')
}

Test-Step 'agent math response' {
    $out = & openclaw agent --agent main --message 'What is 2 + 2?' 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { return $false }
    return ($out.Trim().Length -gt 0)
}

Test-Step 'default agent model configured (see JARVIS_OPENCLAW_EXPECTED_MODEL)' {
    $cfg = Read-OpenClawJson
    if (-not $cfg -or -not $cfg.ContainsKey('agents')) { return $false }
    $agents = $cfg['agents']
    if (-not $agents.ContainsKey('list')) { return $false }
    $list = $agents['list']
    $expected = [Environment]::GetEnvironmentVariable('JARVIS_OPENCLAW_EXPECTED_MODEL', 'User')
    if ([string]::IsNullOrWhiteSpace($expected)) { $expected = $env:JARVIS_OPENCLAW_EXPECTED_MODEL }
    foreach ($item in $list) {
        if ($item['default'] -eq $true) {
            $m = [string]$item['model']
            if ([string]::IsNullOrWhiteSpace($m)) { return $false }
            if (-not [string]::IsNullOrWhiteSpace($expected)) {
                return ($m -eq $expected)
            }
            return $true
        }
    }
    return $false
}

Test-Step 'ollama plugin enabled' {
    $cfg = Read-OpenClawJson
    if (-not $cfg -or -not $cfg.ContainsKey('plugins')) { return $false }
    $p = $cfg['plugins']
    if (-not $p.ContainsKey('entries')) { return $false }
    $e = $p['entries']
    if (-not $e.ContainsKey('ollama')) { return $false }
    $o = $e['ollama']
    if ($null -eq $o) { return $false }
    return ($o['enabled'] -eq $true)
}

Test-Step 'composio plugin enabled' {
    $cfg = Read-OpenClawJson
    if (-not $cfg -or -not $cfg.ContainsKey('plugins')) { return $false }
    $p = $cfg['plugins']
    if (-not $p.ContainsKey('entries')) { return $false }
    $e = $p['entries']
    if (-not $e.ContainsKey('composio')) { return $false }
    $c = $e['composio']
    if ($null -eq $c) { return $false }
    return ($c['enabled'] -eq $true)
}

Write-Host ""
Write-Host "Summary: $pass/6 checks passed." -ForegroundColor $(if ($fail -eq 0) { 'Green' } else { 'Yellow' })
Write-Host "PHASE8 gateway $pass 6"
if ($fail -gt 0) { exit 1 }
exit 0
