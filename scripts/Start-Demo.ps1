[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$server = Join-Path $root 'server'
$venvPython = Join-Path $server '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Run .\scripts\Setup-Demo.ps1 first to install dependencies.'
}
if (-not (Test-Path -LiteralPath (Join-Path $root 'web\dist\index.html'))) {
    throw 'The web build is missing. Run npm --prefix web run build first.'
}

$arguments = @('-m', 'uvicorn', 'caspian.api:app', '--host', '127.0.0.1', '--port', "$Port")
if (Test-Path -LiteralPath (Join-Path $server '.env')) {
    $arguments += @('--env-file', (Join-Path $server '.env'))
}

Write-Output "Caspian Compass: http://127.0.0.1:$Port"
Write-Output 'All bookings and payments are simulated. Press Ctrl+C to stop.'
Push-Location $server
try {
    & $venvPython @arguments
    if ($LASTEXITCODE -ne 0) { throw "The demo server exited with code $LASTEXITCODE." }
} finally {
    Pop-Location
}
