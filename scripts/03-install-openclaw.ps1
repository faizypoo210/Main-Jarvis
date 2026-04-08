<#
.SYNOPSIS
  Installs OpenClaw via WSL2 bash installer when bash is available, then Windows install.ps1 with -NoOnboard, and verifies `openclaw --version`.
#>
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Step "=== JARVIS Phase 3: Install OpenClaw CLI ==="

if (Get-Command openclaw -ErrorAction SilentlyContinue) {
    Write-Ok "OpenClaw is already on PATH; skipping installers."
    openclaw --version
    if ($LASTEXITCODE -ne 0) { Write-Fail "openclaw --version failed"; exit 1 }
    Write-Ok "openclaw --version OK"
    exit 0
}

# Optional: official bash installer inside WSL (only if bash exists)
if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    $prevEa = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $bashOk = $false
    try {
        & wsl.exe -e bash -lc "echo wsl-bash-ok" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $bashOk = $true }
    } finally {
        $ErrorActionPreference = $prevEa
    }
    if ($bashOk) {
        Write-Step "Running official install.sh via WSL2 (no onboarding)..."
        $ErrorActionPreference = "Continue"
        try {
            & wsl.exe -e bash -lc "curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard" 2>&1 | ForEach-Object { Write-Host $_ }
        } finally {
            $ErrorActionPreference = "Stop"
        }
    } else {
        Write-Host "[SKIP] WSL bash not available; using Windows installer only." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "[SKIP] wsl.exe not found; using Windows installer only." -ForegroundColor DarkYellow
}

Write-Step "Downloading and running official install.ps1 on Windows (no onboarding)..."
$tmp = Join-Path $env:TEMP "openclaw-install-$(New-Guid).ps1"
try {
    Invoke-WebRequest -Uri "https://openclaw.ai/install.ps1" -OutFile $tmp -UseBasicParsing
    & $tmp -NoOnboard
} finally {
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
    Write-Fail "openclaw is still not on PATH after install. Restart the terminal or add npm global bin to PATH."
    exit 1
}

Write-Step "Verifying openclaw --version..."
openclaw --version
if ($LASTEXITCODE -ne 0) { Write-Fail "openclaw --version exited non-zero"; exit 1 }

Write-Ok "OpenClaw CLI installed and `openclaw --version` succeeded."
exit 0
