$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $root ".desktop_companion_venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$envFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Desktop companion is not installed. Run .\desktop_companion\install.ps1 first."
}

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing desktop_companion\.env. Copy .env.example to .env and configure MONGODB_URL."
}

$env:PYTHONPATH = Join-Path $root "backend"
$env:HOST = "127.0.0.1"
$env:PORT = "8000"

Write-Host "Starting Fitness AI Desktop Tracker Companion on http://127.0.0.1:8000"
Write-Host "Keep this window open while using live exercise tracking."

Set-Location -LiteralPath $root
& $pythonExe -m uvicorn desktop_companion.companion_app:app --host 127.0.0.1 --port 8000
