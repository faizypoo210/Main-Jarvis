#Requires -Version 5.1
# Phase 6: Verify Composio CLI, local plugin install, TOOLS.md, openclaw.json plugin; optional Gmail execute test.
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Web.Extensions

$coreOk = $true

# 1) composio CLI
if (-not (Get-Command composio -ErrorAction SilentlyContinue)) {
    Write-Host "FAIL: composio CLI not on PATH."
    $coreOk = $false
} else {
    Write-Host "PASS: composio CLI is available."
}

# 2) global composio-core
$npmList = npm list -g composio-core --depth=0 2>&1 | Out-String
if ($npmList -notmatch 'composio-core@') {
    Write-Host "FAIL: composio-core not listed in npm global packages."
    $coreOk = $false
} else {
    Write-Host "PASS: composio-core is installed globally."
    Write-Host $npmList.Trim()
}

# 3) @composio/openclaw-plugin under ~/.openclaw
$pluginPath = Join-Path $env:USERPROFILE '.openclaw\node_modules\@composio\openclaw-plugin'
if (-not (Test-Path $pluginPath)) {
    Write-Host "FAIL: Missing $pluginPath"
    $coreOk = $false
} else {
    Write-Host "PASS: @composio/openclaw-plugin is present under %USERPROFILE%\.openclaw"
}

# 4) TOOLS.md
$toolsMd = Join-Path $env:USERPROFILE '.openclaw\workspace\main\TOOLS.md'
if (-not (Test-Path $toolsMd)) {
    Write-Host "FAIL: TOOLS.md not found at $toolsMd"
    $coreOk = $false
} else {
    Write-Host "PASS: TOOLS.md exists at $toolsMd"
}

# 5) openclaw.json plugins.entries.composio
$ocPath = Join-Path $env:USERPROFILE '.openclaw\openclaw.json'
if (-not (Test-Path $ocPath)) {
    Write-Host "FAIL: openclaw.json missing at $ocPath"
    $coreOk = $false
} else {
    $raw = Get-Content -Path $ocPath -Raw -Encoding UTF8
    $ser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $ser.MaxJsonLength = 67108864
    $cfg = $ser.DeserializeObject($raw)
    $ok = $false
    if ($cfg -and $cfg.ContainsKey('plugins')) {
        $p = $cfg['plugins']
        if ($p -and $p.ContainsKey('entries')) {
            $e = $p['entries']
            if ($e -and $e.ContainsKey('composio')) {
                $c = $e['composio']
                if ($c -and $c.ContainsKey('enabled') -and [bool]$c['enabled']) {
                    $ok = $true
                }
            }
        }
    }
    if ($ok) {
        Write-Host "PASS: openclaw.json has plugins.entries.composio.enabled = true"
    } else {
        Write-Host "FAIL: plugins.entries.composio.enabled = true not found in openclaw.json"
        $coreOk = $false
    }
}

# 6) connections (informational)
Write-Host ""
Write-Host "--- composio connections (informational) ---"
try {
    & composio connections 2>&1 | Write-Host
} catch {
    Write-Host "WARN: composio connections failed (may need login): $_"
}

# 7) Optional Gmail read-only test
Write-Host ""
Write-Host "--- Gmail tool test (optional; fails if Gmail not connected) ---"
$gmailOk = $false
try {
    $exeOut = & composio execute GMAIL_GET_PROFILE -p '{}' 2>&1 | Out-String
    Write-Host $exeOut
    if ($LASTEXITCODE -eq 0 -and $exeOut -notmatch '(?i)Error executing|API Key|status code (4|5)\d\d') {
        $gmailOk = $true
    }
} catch {
    Write-Host "WARN: composio execute GMAIL_GET_PROFILE threw: $_"
}

if ($gmailOk) {
    Write-Host "PASS: GMAIL_GET_PROFILE appears successful."
} else {
    Write-Host "INFO: Gmail execute check did not pass (OAuth or COMPOSIO_API_KEY may be missing). This is OK for Phase 6 verify."
}

if (-not $coreOk) {
    Write-Host ""
    Write-Host "Core verification failed."
    exit 1
}

Write-Host ""
Write-Host "Phase 6 verification passed (core checks OK; Gmail OAuth optional)."
exit 0
