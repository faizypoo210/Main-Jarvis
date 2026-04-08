#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$RepoUrl = 'https://github.com/Curbob/LobsterBoard'
$Target = 'C:\projects\LobsterBoard'

if (-not (Test-Path $Target)) {
    $parent = Split-Path -Parent $Target
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Write-Host "Cloning LobsterBoard to $Target ..."
    git clone $RepoUrl $Target
} else {
    Write-Host "LobsterBoard already exists at $Target - skipping clone."
}

Push-Location $Target
try {
    Write-Host "Running npm install in $Target ..."
    npm install
} finally {
    Pop-Location
}

$serverCjs = Join-Path $Target 'server.cjs'
if (-not (Test-Path $serverCjs)) {
    throw "server.cjs not found at $serverCjs after install."
}

Write-Host "LobsterBoard install completed successfully."
