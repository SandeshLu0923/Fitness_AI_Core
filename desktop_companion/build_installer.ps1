$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $root ".desktop_companion_build_venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$specPath = Join-Path $PSScriptRoot "FitnessAI-Desktop-Tracker.spec"
$distApp = Join-Path $root "dist\FitnessAI-Desktop-Tracker"
$installerScript = Join-Path $PSScriptRoot "installer.iss"
$installerOutput = Join-Path $root "release\installer"

function Resolve-Python311 {
    $projectPython = Join-Path $root "venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $projectPython) {
        try {
            $versionOutput = & $projectPython --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $versionOutput -match "Python 3\.11") {
                return @{ Exe = $projectPython; Arg = "" }
            }
        } catch {
            # Continue to global Python checks below.
        }
    }

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

    throw "Python 3.11 is required. Install Python 3.11, then run this build again."
}

if (-not (Test-Path -LiteralPath $venvPath)) {
    $python = Resolve-Python311
    Write-Host "Creating desktop companion build environment with Python 3.11..."
    if ($python.Arg) {
        & $python.Exe $python.Arg -m venv $venvPath
    } else {
        & $python.Exe -m venv $venvPath
    }
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Build Python environment was not created correctly: $pythonExe"
}

Write-Host "Installing build dependencies..."
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $root "backend\requirements.txt")
& $pythonExe -m pip install pyinstaller==6.10.0

Write-Host "Building desktop app with PyInstaller..."
Set-Location -LiteralPath $root
& $pythonExe -m PyInstaller --clean --noconfirm $specPath

if (-not (Test-Path -LiteralPath $distApp)) {
    throw "PyInstaller output was not created: $distApp"
}

Write-Host "Desktop app folder created: $distApp"

$iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidatePaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )

    foreach ($candidatePath in $candidatePaths) {
        if (Test-Path -LiteralPath $candidatePath) {
            $iscc = @{ Source = $candidatePath }
            break
        }
    }
}

if ($iscc) {
    New-Item -ItemType Directory -Path $installerOutput -Force | Out-Null
    Write-Host "Building Windows installer with Inno Setup..."
    & $iscc.Source $installerScript
    Write-Host "Installer created: $(Join-Path $installerOutput 'FitnessAI-Desktop-Tracker-Setup.exe')"
} else {
    Write-Warning "Inno Setup was not found. Install Inno Setup 6 to create Setup.exe."
    Write-Host "You can still zip and run this folder: $distApp"
}
