param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$EnvFile = Join-Path $Root ".env"
$EntryPoint = Join-Path $Root "wxsph_api\wxsph_api.py"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run .\setup_local.ps1 first."
}

if (-not (Test-Path $EnvFile)) {
    throw ".env not found. Run .\setup_local.ps1 first, then configure .env."
}

Set-Location $Root
$env:WXSPH_HOST = $HostAddress
$env:WXSPH_PORT = [string]$Port

Write-Host "Starting optional wxsph parser at http://${HostAddress}:$Port"
& $Python $EntryPoint
