[CmdletBinding()]
param(
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$server = Join-Path $root 'server'
$web = Join-Path $root 'web'

if (-not (Test-Path -LiteralPath (Join-Path $server 'requirements.txt'))) {
    throw 'The server dependency manifest is missing. Use a complete checkout.'
}
if (-not (Test-Path -LiteralPath (Join-Path $web 'package.json'))) {
    throw 'The web dependency manifest is missing. Use a complete checkout.'
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv (https://docs.astral.sh/uv/getting-started/installation/) and run setup again.'
}

& uv sync --project $server --frozen --group dev --python $Python
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

Push-Location $web
try {
    if (Test-Path -LiteralPath 'package-lock.json') {
        & npm ci --no-audit --no-fund
    } else {
        & npm install --no-audit --no-fund
    }
    if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed.' }
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'The web build failed.' }
} finally {
    Pop-Location
}

Write-Output 'Setup complete. Run .\scripts\Start-Demo.ps1 to start Caspian Compass.'
