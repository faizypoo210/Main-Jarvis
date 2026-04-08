#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$listen = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)
if ($listen.Count -eq 0) {
    throw "Port 8080 is not listening - LobsterBoard does not appear to be running."
}

try {
    $resp = Invoke-WebRequest -Uri 'http://localhost:8080' -UseBasicParsing -TimeoutSec 15
} catch {
    throw "HTTP GET http://localhost:8080 failed: $_"
}

if ($resp.StatusCode -ne 200) {
    throw "Expected HTTP 200 from http://localhost:8080, got $($resp.StatusCode)."
}

Write-Host "LobsterBoard is reachable at http://localhost:8080 (HTTP $($resp.StatusCode))."
Write-Host "On the same WiFi, open http://10.0.0.249:8080 from your phone to reach this dashboard."
