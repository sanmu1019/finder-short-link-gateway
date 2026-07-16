param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8790
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$EnvFile = Join-Path $Root ".env"
$AppDir = Join-Path $Root "finder_gateway"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run .\setup_local.ps1 first."
}

if (-not (Test-Path $EnvFile)) {
    throw ".env not found. Run .\setup_local.ps1 first, then configure .env."
}

Set-Location $Root

Write-Host "Starting Finder gateway at http://${HostAddress}:$Port"
Write-Host "Chromium will open automatically. Keep this window running."

& $Python -m uvicorn app.main:app `
    --app-dir $AppDir `
    --host $HostAddress `
    --port $Port `
    --env-file $EnvFile `
    --no-access-log
