$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$modelsDir = Join-Path $root "backend\app"
$tempDir = Join-Path $root ".model_downloads"

$defaultBaseUrl = "https://github.com/SandeshLu0923/Fitness_AI_Core/releases/latest/download"
$baseUrl = if ($env:FITNESS_AI_MODELS_BASE_URL) { $env:FITNESS_AI_MODELS_BASE_URL.TrimEnd("/") } else { $defaultBaseUrl }
$manifestName = "fitness-ai-tracker-models-manifest.json"
$manifestPath = Join-Path $tempDir $manifestName

if (Test-Path -LiteralPath $tempDir) {
    Remove-Item -LiteralPath $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

Write-Host "Downloading model manifest..."
Invoke-WebRequest -Uri "$baseUrl/$manifestName" -OutFile $manifestPath -UseBasicParsing

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

foreach ($model in $manifest) {
    $targetPath = Join-Path $modelsDir $model.file
    Write-Host "Downloading $($model.file)..."

    $outputStream = [System.IO.File]::Open($targetPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    try {
        foreach ($partName in $model.parts) {
            $partPath = Join-Path $tempDir $partName
            Invoke-WebRequest -Uri "$baseUrl/$partName" -OutFile $partPath -UseBasicParsing
            $partBytes = [System.IO.File]::ReadAllBytes($partPath)
            $outputStream.Write($partBytes, 0, $partBytes.Length)
        }
    } finally {
        $outputStream.Close()
    }

    $actualSize = (Get-Item -LiteralPath $targetPath).Length
    if ($actualSize -ne [int64]$model.size) {
        throw "Model size mismatch for $($model.file). Expected $($model.size), got $actualSize."
    }
}

Remove-Item -LiteralPath $tempDir -Recurse -Force
Write-Host "Model files installed into backend\app."
