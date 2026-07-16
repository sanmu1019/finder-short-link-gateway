$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Requirements = Join-Path $Root "finder_gateway\requirements.txt"
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"

Set-Location $Root

if (-not (Test-Path $Python)) {
    Write-Host "Creating virtual environment: $Venv"
    python -m venv $Venv
}

Write-Host "Installing Python dependencies..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -r $Requirements

Write-Host "Installing Playwright Chromium..."
& $Python -m playwright install chromium

if (-not (Test-Path $EnvFile)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    Write-Host "Created .env from .env.example"
}

Write-Host ""
Write-Host "Local setup completed."
Write-Host "Edit .env and replace FINDER_API_KEY before starting."
Write-Host "Start with: .\start_local.ps1"
