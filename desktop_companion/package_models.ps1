$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $root "release\models"
$chunkSizeBytes = 24MB

if (Test-Path -LiteralPath $distDir) {
    Remove-Item -LiteralPath $distDir -Recurse -Force
}
New-Item -ItemType Directory -Path $distDir | Out-Null

$modelNames = @(
    "exercise_phase_models.joblib",
    "pose_state_model.joblib",
    "pose_model.joblib",
    "habit_model.joblib"
)

$manifest = @()

foreach ($modelName in $modelNames) {
    $source = Join-Path $root "backend\app\$modelName"
    if (-not (Test-Path -LiteralPath $source)) {
        Write-Warning "Skipping missing model: $modelName"
        continue
    }

    $bytes = [System.IO.File]::ReadAllBytes($source)
    $partCount = [Math]::Ceiling($bytes.Length / $chunkSizeBytes)
    $parts = @()

    for ($partIndex = 0; $partIndex -lt $partCount; $partIndex++) {
        $offset = $partIndex * $chunkSizeBytes
        $count = [Math]::Min($chunkSizeBytes, $bytes.Length - $offset)
        $partName = "{0}.part{1:D2}.zip" -f $modelName, ($partIndex + 1)
        $partPath = Join-Path $distDir $partName
        $partBytes = New-Object byte[] $count
        [Array]::Copy($bytes, $offset, $partBytes, 0, $count)
        [System.IO.File]::WriteAllBytes($partPath, $partBytes)
        $parts += $partName
    }

    $manifest += [ordered]@{
        file = $modelName
        size = $bytes.Length
        parts = $parts
    }
}

$manifestPath = Join-Path $distDir "fitness-ai-tracker-models-manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding ASCII

$readme = @"
Fitness AI tracker model release assets.

Upload every file in this folder to the same GitHub Release:
- fitness-ai-tracker-models-manifest.json
- *.partNN files

Each chunk is below 25 MB for GitHub browser upload.
"@
Set-Content -LiteralPath (Join-Path $distDir "README-model-assets.txt") -Value $readme -Encoding ASCII

Write-Host "Created model release assets:"
Get-ChildItem -LiteralPath $distDir -File | Sort-Object Name | ForEach-Object {
    Write-Host ("- {0} ({1} MB)" -f $_.FullName, [math]::Round($_.Length / 1MB, 2))
}
