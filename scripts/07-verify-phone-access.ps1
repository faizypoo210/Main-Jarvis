#Requires -Version 5.1
# Phase 7: Print LAN URLs and probe each with HTTP GET (informational; always exits 0).
$ErrorActionPreference = 'Continue'

$LanIp = '10.0.0.249'
$urls = @(
    @{ Label = 'Mission Control UI';  Url = "http://${LanIp}:3000" },
    @{ Label = 'Mission Control API'; Url = "http://${LanIp}:3001/health" },
    @{ Label = 'OpenClaw Gateway';    Url = "http://${LanIp}:18789" },
    @{ Label = 'LobsterBoard';        Url = "http://${LanIp}:8080" },
    @{ Label = 'Ollama';              Url = "http://${LanIp}:11434" }
)

Write-Host "LAN base address: $LanIp (same WiFi as this PC)" -ForegroundColor Cyan
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
