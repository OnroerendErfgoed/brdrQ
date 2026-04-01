param(
    [string[]]$Tests = @(),
    [string]$QgisPython = "C:\Program Files\QGIS 3.38.1\bin\python.exe",
    [string]$ProjPath = "C:\Program Files\QGIS 3.38.1\share\proj"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $QgisPython)) {
    throw "QGIS Python not found: $QgisPython"
}

if (-not (Test-Path $ProjPath)) {
    throw "PROJ path not found: $ProjPath"
}

$env:PROJ_LIB = $ProjPath
$env:PROJ_DATA = $ProjPath

if ($Tests.Count -eq 0) {
    $Tests = Get-ChildItem -Path "plugin/brdrq/test" -Filter "test_*.py" |
        Sort-Object Name |
        ForEach-Object { $_.FullName }
}

Write-Host "Using QGIS Python: $QgisPython"
Write-Host "Using PROJ path: $ProjPath"
Write-Host "Running tests:" ($Tests -join ", ")

& $QgisPython -m pytest @Tests
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    throw "pytest failed with exit code $exitCode"
}

Write-Host "Tests passed."
