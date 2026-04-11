#Requires -Version 5.1
# Phase 7: Print LAN URLs and probe each with HTTP GET (informational; always exits 0).
$ErrorActionPreference = 'Continue'

$LanIp = [Environment]::GetEnvironmentVariable('JARVIS_LAN_IP', 'User')
if ([string]::IsNullOrWhiteSpace($LanIp)) { $LanIp = $env:JARVIS_LAN_IP }
if ([string]::IsNullOrWhiteSpace($LanIp)) { $LanIp = '127.0.0.1' }
$urls = @(
    @{ Label = 'Command Center (primary UI)'; Url = "http://${LanIp}:5173" },
    @{ Label = 'Control Plane /health';      Url = "http://${LanIp}:8001/health" },
    @{ Label = 'Voice Server';              Url = "http://${LanIp}:8000" },
    @{ Label = 'OpenClaw Gateway';          Url = "http://${LanIp}:18789" },
    @{ Label = 'LobsterBoard';              Url = "http://${LanIp}:8080" },
    @{ Label = 'Ollama';                    Url = "http://${LanIp}:11434" }
)

Write-Host "LAN base address: $LanIp (set User env JARVIS_LAN_IP to your Wi‑Fi IPv4 for phone access)" -ForegroundColor Cyan
Write-Host ""

foreach ($u in $urls) {
    try {
        $resp = Invoke-WebRequest -Uri $u.Url -UseBasicParsing -TimeoutSec 12 -ErrorAction Stop
        $code = $resp.StatusCode
        Write-Host "PASS: $($u.Label) -> $($u.Url) (HTTP $code)"
    } catch {
        Write-Host "FAIL: $($u.Label) -> $($u.Url) ($($_.Exception.Message))"
    }
}

Write-Host ""
Write-Host "Open these URLs from your phone browser while on the same WiFi to verify access." -ForegroundColor Yellow
exit 0
