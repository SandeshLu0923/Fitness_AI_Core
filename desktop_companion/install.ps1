$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $root ".desktop_companion_venv"

function Resolve-Python311 {
    $candidates = @(
        @("py", "-3.11"),
        @("python", "")
    )

    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $arg = $candidate[1]
        try {
            $versionOutput = if ($arg) {
                & $exe $arg --version 2>&1
            } else {
                & $exe --version 2>&1
            }
            if ($LASTEXITCODE -eq 0 -and $versionOutput -match "Python 3\.11") {
                return @{ Exe = $exe; Arg = $arg }
            }
        } catch {
            continue
        }
    }

    throw "Python 3.11 is required. Install Python 3.11, then run this installer again."
}

if (-not (Test-Path -LiteralPath $venvPath)) {
    $python = Resolve-Python311
    Write-Host "Creating desktop companion environment with Python 3.11..."
    if ($python.Arg) {
        & $python.Exe $python.Arg -m venv $venvPath
    } else {
        & $python.Exe -m venv $venvPath
    }
}

$pythonExe = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Companion Python environment was not created correctly: $pythonExe"
}

Write-Host "Installing desktop companion dependencies..."
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $root "backend\requirements.txt")

if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot ".env"))) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.example") -Destination (Join-Path $PSScriptRoot ".env")
    Write-Host "Created desktop_companion\.env from template. Add your MongoDB URL before starting."
}

Write-Host "Desktop companion installed."
Write-Host "Start it with: powershell -ExecutionPolicy Bypass -File .\desktop_companion\start.ps1"
