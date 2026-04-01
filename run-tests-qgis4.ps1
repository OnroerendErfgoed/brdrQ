param(
    [string[]]$Tests = @(),
    [string]$QgisPython = "",
    [string]$ProjPath = "",
    [ValidateSet("smoke", "all")]
    [string]$Suite = "smoke",
    [ValidateSet("perfile", "batch")]
    [string]$Mode = "perfile"
)

$ErrorActionPreference = "Stop"

function Find-Qgis4Python {
    param([string]$OverridePath)

    if ($OverridePath -and (Test-Path $OverridePath)) {
        return $OverridePath
    }

    $candidates = @(
        "C:\Program Files\QGIS 4\bin\python.exe",
        "C:\Program Files\QGIS 4.0\bin\python.exe",
        "C:\Program Files\QGIS 4.1\bin\python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $qgisDirs = Get-ChildItem "C:\Program Files" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "QGIS 4*" } |
        Sort-Object Name -Descending

    foreach ($dir in $qgisDirs) {
        $pythonPath = Join-Path $dir.FullName "bin\python.exe"
        if (Test-Path $pythonPath) {
            return $pythonPath
        }
    }

    return $null
}

function Find-Qgis4ProjPath {
    param([string]$OverridePath, [string]$ResolvedPython)

    if ($OverridePath -and (Test-Path $OverridePath)) {
        return $OverridePath
    }

    if ($ResolvedPython) {
        $qgisRoot = Split-Path (Split-Path $ResolvedPython -Parent) -Parent
        $projFromPython = Join-Path $qgisRoot "share\proj"
        if (Test-Path $projFromPython) {
            return $projFromPython
        }
    }

    $candidates = @(
        "C:\Program Files\QGIS 4\share\proj",
        "C:\Program Files\QGIS 4.0\share\proj",
        "C:\Program Files\QGIS 4.1\share\proj"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $qgisDirs = Get-ChildItem "C:\Program Files" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "QGIS 4*" } |
        Sort-Object Name -Descending

    foreach ($dir in $qgisDirs) {
        $projPath = Join-Path $dir.FullName "share\proj"
        if (Test-Path $projPath) {
            return $projPath
        }
    }

    return $null
}

function Invoke-InQgisWindowsEnv {
    param(
        [string]$QgisRoot,
        [string]$CommandLine
    )

    $binDir = Join-Path $QgisRoot "bin"
    $o4wEnv = Join-Path $binDir "o4w_env.bat"
    $qtEnv = Join-Path $binDir "qt6_env.bat"
    if (-not (Test-Path $o4wEnv)) {
        throw "Missing o4w_env.bat in $binDir"
    }

    $tempBat = [System.IO.Path]::GetTempFileName() + ".bat"
    @(
        "@echo off",
        "call `"$o4wEnv`"",
        "if exist `"$qtEnv`" call `"$qtEnv`"",
        "set `"QGIS_PREFIX_PATH=$QgisRoot`"",
        "set `"PYTHONHOME=`"",
        "set `"PYTHONUTF8=1`"",
        $CommandLine,
        "exit /b %errorlevel%"
    ) | Set-Content -Path $tempBat -Encoding ASCII

    try {
        & cmd.exe /c $tempBat | ForEach-Object { Write-Host $_ }
        return [int]$LASTEXITCODE
    }
    finally {
        Remove-Item -Path $tempBat -Force -ErrorAction SilentlyContinue
    }
}

$resolvedPython = Find-Qgis4Python -OverridePath $QgisPython
if (-not $resolvedPython) {
    throw "QGIS 4 Python not found. Provide -QgisPython explicitly, e.g. C:\Program Files\QGIS 4\bin\python.exe"
}

$resolvedProj = Find-Qgis4ProjPath -OverridePath $ProjPath -ResolvedPython $resolvedPython
if (-not $resolvedProj) {
    throw "QGIS 4 PROJ path not found. Provide -ProjPath explicitly, e.g. C:\Program Files\QGIS 4\share\proj"
}

$qgisBin = Split-Path $resolvedPython -Parent
$qgisRoot = Split-Path $qgisBin -Parent
$pythonQgisBat = Join-Path $qgisRoot "bin\python-qgis.bat"
$qgisAppBin = Join-Path $qgisRoot "apps\qgis\bin"
$qgisGdalData = Join-Path $qgisRoot "share\gdal"
$qgisPythonPath = Join-Path $qgisRoot "apps\qgis\python"
$qgisPythonPluginsPath = Join-Path $qgisRoot "apps\qgis\python\plugins"
$qt6Bin = Join-Path $qgisRoot "apps\Qt6\bin"
$qt5Bin = Join-Path $qgisRoot "apps\Qt5\bin"
$pythonRuntimeRoot = $null
$pythonRuntimeDlls = $null
$pythonRuntimeLibBin = $null
$qgisPythonSitePackages = Get-ChildItem -Path (Join-Path $qgisRoot "apps") -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "Python*" } |
    ForEach-Object { Join-Path $_.FullName "Lib\site-packages" } |
    Where-Object { Test-Path $_ } |
    Select-Object -First 1
$qt6Plugins = Join-Path $qgisRoot "apps\Qt6\plugins"
$qt5Plugins = Join-Path $qgisRoot "apps\Qt5\plugins"

# Ensure QGIS binaries are first on PATH to avoid mixed DLL loading.
$pathParts = @()
if (Test-Path $qgisAppBin) { $pathParts += $qgisAppBin }
if (Test-Path $qgisBin) { $pathParts += $qgisBin }
if (Test-Path $qt6Bin) { $pathParts += $qt6Bin }
if (Test-Path $qt5Bin) { $pathParts += $qt5Bin }

$pythonRuntimeCandidates = Get-ChildItem -Path (Join-Path $qgisRoot "apps") -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "Python*" } |
    Sort-Object Name -Descending
if ($pythonRuntimeCandidates.Count -gt 0) {
    $pythonRuntimeRoot = $pythonRuntimeCandidates[0].FullName
    $pythonRuntimeDlls = Join-Path $pythonRuntimeRoot "DLLs"
    $pythonRuntimeLibBin = Join-Path $pythonRuntimeRoot "Library\bin"
    if (Test-Path $pythonRuntimeRoot) { $pathParts += $pythonRuntimeRoot }
    if (Test-Path $pythonRuntimeDlls) { $pathParts += $pythonRuntimeDlls }
    if (Test-Path $pythonRuntimeLibBin) { $pathParts += $pythonRuntimeLibBin }
}
$pathParts += $env:PATH
$env:PATH = ($pathParts -join ";")

# Avoid contamination from another installed QGIS/Python environment.
$env:PYTHONHOME = $null
$env:PYTHONPATH = ""
if (Test-Path $qgisPythonPath) {
    $env:PYTHONPATH = $qgisPythonPath
}
if (Test-Path $qgisPythonPluginsPath) {
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$env:PYTHONPATH;$qgisPythonPluginsPath"
    } else {
        $env:PYTHONPATH = $qgisPythonPluginsPath
    }
}
if ($qgisPythonSitePackages) {
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$env:PYTHONPATH;$qgisPythonSitePackages"
    } else {
        $env:PYTHONPATH = $qgisPythonSitePackages
    }
}

$isWindowsHost = $env:OS -eq "Windows_NT"

$env:QGIS_PREFIX_PATH = $qgisRoot
$env:PROJ_LIB = $resolvedProj
$env:PROJ_DATA = $resolvedProj
if (Test-Path $qgisGdalData) {
    $env:GDAL_DATA = $qgisGdalData
}

# On Windows, forcing QT plugin/platform values can crash Qt6-based builds.
# Prefer QGIS defaults unless explicitly provided by the caller.
if (-not $isWindowsHost) {
    if (-not $env:QT_PLUGIN_PATH) {
        if (Test-Path $qt6Plugins) {
            $env:QT_PLUGIN_PATH = $qt6Plugins
        } elseif (Test-Path $qt5Plugins) {
            $env:QT_PLUGIN_PATH = $qt5Plugins
        }
    }
    if (-not $env:QT_QPA_PLATFORM) {
        $env:QT_QPA_PLATFORM = "offscreen"
    }
}

if ($Tests.Count -eq 0) {
    if ($Suite -eq "all") {
        $Tests = Get-ChildItem -Path "plugin/brdrq/test" -Filter "test_*.py" |
            Sort-Object Name |
            ForEach-Object { $_.FullName }
    } else {
        $Tests = @(
            "plugin/brdrq/test/test_init.py",
            "plugin/brdrq/test/test_toolbar.py",
            "plugin/brdrq/test/test_utils.py",
            "plugin/brdrq/test/test_brdrqdockwidgetfeaturealigner.py"
        )
    }
}

Write-Host "Using QGIS Python:" $resolvedPython
Write-Host "python-qgis.bat:" $(if (Test-Path $pythonQgisBat) { $pythonQgisBat } else { "<not found>" })
Write-Host "QGIS root:" $qgisRoot
Write-Host "Using PROJ path:" $resolvedProj
Write-Host "Qt bin:" $(if (Test-Path $qt6Bin) { $qt6Bin } elseif (Test-Path $qt5Bin) { $qt5Bin } else { "<not found>" })
Write-Host "Python runtime root:" $(if ($pythonRuntimeRoot) { $pythonRuntimeRoot } else { "<not found>" })
Write-Host "PYTHONPATH:" $(if ($env:PYTHONPATH) { $env:PYTHONPATH } else { "<unset>" })
Write-Host "QT_QPA_PLATFORM:" $(if ($env:QT_QPA_PLATFORM) { $env:QT_QPA_PLATFORM } else { "<unset>" })
Write-Host "QT_PLUGIN_PATH:" $(if ($env:QT_PLUGIN_PATH) { $env:QT_PLUGIN_PATH } else { "<unset>" })
Write-Host "Suite:" $Suite
Write-Host "Mode:" $Mode
Write-Host "Running tests:" ($Tests -join ", ")

# Quick sanity check before pytest: can QGIS initialize at all?
Write-Host ""
Write-Host "Running QGIS init sanity check..."
$sanityPy = Join-Path ([System.IO.Path]::GetTempPath()) ("qgis4_sanity_" + [guid]::NewGuid().ToString("N") + ".py")
@(
    "import importlib.util",
    "import sys",
    "print('sys.executable=', sys.executable)",
    "spec = importlib.util.find_spec('qgis')",
    "print('qgis spec=', spec.origin if spec else None)",
    "from qgis.core import QgsApplication",
    "app = QgsApplication([], False)",
    "app.setPrefixPath(r'$qgisRoot', True)",
    "app.initQgis()",
    "print('QGIS init OK')",
    "app.exitQgis()"
) | Set-Content -Path $sanityPy -Encoding ASCII

if ($isWindowsHost) {
    if (Test-Path $pythonQgisBat) {
        $sanityCmd = "`"$pythonQgisBat`" `"$sanityPy`""
    } else {
        $sanityCmd = "`"$resolvedPython`" `"$sanityPy`""
    }
    $sanityExit = Invoke-InQgisWindowsEnv -QgisRoot $qgisRoot -CommandLine $sanityCmd
}
else {
    & $resolvedPython $sanityPy
    $sanityExit = $LASTEXITCODE
}
Remove-Item -Path $sanityPy -Force -ErrorAction SilentlyContinue
if ($sanityExit -ne 0) {
    throw "QGIS sanity check failed with exit code $sanityExit. QGIS4 environment is unstable before pytest starts."
}

if ($Mode -eq "perfile") {
    $perFileFailures = @()
    foreach ($testFile in $Tests) {
        Write-Host ""
        Write-Host ">>> Running $testFile"
        if ($isWindowsHost) {
            if (Test-Path $pythonQgisBat) {
                $testCmd = "`"$pythonQgisBat`" -m pytest -q `"$testFile`""
            } else {
                $testCmd = "`"$resolvedPython`" -m pytest -q `"$testFile`""
            }
            $singleExit = Invoke-InQgisWindowsEnv -QgisRoot $qgisRoot -CommandLine $testCmd
        }
        else {
            & $resolvedPython -m pytest -q $testFile
            $singleExit = $LASTEXITCODE
        }
        if ($singleExit -ne 0) {
            $perFileFailures += "$testFile (exit $singleExit)"
        }
    }

    if ($perFileFailures.Count -gt 0) {
        Write-Host ""
        Write-Host "Per-file failures:"
        $perFileFailures | ForEach-Object { Write-Host " - $_" }
        throw "pytest failed for one or more test files"
    }

    Write-Host ""
    Write-Host "Tests passed."
    exit 0
}

if ($isWindowsHost) {
    $quotedTests = $Tests | ForEach-Object { "`"$_`"" }
    if (Test-Path $pythonQgisBat) {
        $batchCmd = "`"$pythonQgisBat`" -m pytest " + ($quotedTests -join " ")
    } else {
        $batchCmd = "`"$resolvedPython`" -m pytest " + ($quotedTests -join " ")
    }
    $exitCode = Invoke-InQgisWindowsEnv -QgisRoot $qgisRoot -CommandLine $batchCmd
}
else {
    & $resolvedPython -m pytest @Tests
    $exitCode = $LASTEXITCODE
}

if ($exitCode -ne 0) {
    if ($exitCode -eq -1073741819) {
        throw "pytest failed with exit code $exitCode (0xC0000005 Access Violation). Try -Mode perfile to isolate unstable tests."
    }
    throw "pytest failed with exit code $exitCode"
}

Write-Host "Tests passed."
