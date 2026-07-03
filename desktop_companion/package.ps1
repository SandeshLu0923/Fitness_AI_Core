$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $root "release"
$stagingDir = Join-Path $distDir "FitnessAI-Desktop-Tracker"
$zipPath = Join-Path $distDir "FitnessAI-Desktop-Tracker.zip"

if (Test-Path -LiteralPath $stagingDir) {
    Remove-Item -LiteralPath $stagingDir -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $stagingDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stagingDir "backend") | Out-Null

Copy-Item -LiteralPath (Join-Path $root "desktop_companion") -Destination (Join-Path $stagingDir "desktop_companion") -Recurse
Copy-Item -LiteralPath (Join-Path $root "backend\app") -Destination (Join-Path $stagingDir "backend\app") -Recurse
Copy-Item -LiteralPath (Join-Path $root "backend\requirements.txt") -Destination (Join-Path $stagingDir "backend\requirements.txt")
Copy-Item -LiteralPath (Join-Path $root "backend\.python-version") -Destination (Join-Path $stagingDir "backend\.python-version") -ErrorAction SilentlyContinue
Copy-Item -LiteralPath (Join-Path $root "backend\runtime.txt") -Destination (Join-Path $stagingDir "backend\runtime.txt") -ErrorAction SilentlyContinue

$cacheDirs = Get-ChildItem -LiteralPath $stagingDir -Recurse -Directory -Filter "__pycache__"
foreach ($cacheDir in $cacheDirs) {
    Remove-Item -LiteralPath $cacheDir.FullName -Recurse -Force
}

$datasetFiles = Get-ChildItem -LiteralPath (Join-Path $stagingDir "backend\app") -Recurse -File | Where-Object {
    $_.Extension -eq ".csv"
}
foreach ($datasetFile in $datasetFiles) {
    Remove-Item -LiteralPath $datasetFile.FullName -Force
}

$secretEnv = Join-Path $stagingDir "desktop_companion\.env"
if (Test-Path -LiteralPath $secretEnv) {
    Remove-Item -LiteralPath $secretEnv -Force
}

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force

Write-Host "Created $zipPath"
Write-Host "Upload this single file to GitHub Releases as FitnessAI-Desktop-Tracker.zip"
