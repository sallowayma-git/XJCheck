param(
    [string]$Python = "python",
    [string]$OdaSourceDir = "",
    [switch]$SkipOda,
    [switch]$SkipSidecar,
    [switch]$SkipFrontend,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopDir = Resolve-Path (Join-Path $ScriptDir "..")
$RepoRoot = Resolve-Path (Join-Path $DesktopDir "..\..")
$TauriDir = Join-Path $DesktopDir "src-tauri"
$SidecarDir = Join-Path $TauriDir "resources\sidecar"
$OdaDir = Join-Path $TauriDir "resources\oda"

Write-Host "=== DWG Audit Desktop Windows release build ==="
Write-Host "Repo: $RepoRoot"
Write-Host "Desktop: $DesktopDir"

Push-Location $DesktopDir
try {
    if (-not $SkipOda) {
        Write-Host "`n[1/4] Stage ODA File Converter resources"
        $stageArgs = @("-File", (Join-Path $ScriptDir "stage-oda-resources.ps1"))
        if ($OdaSourceDir) {
            $stageArgs += @("-SourceDir", $OdaSourceDir)
        }
        if ($Clean) {
            $stageArgs += "-Clean"
        }
        & powershell -NoProfile -ExecutionPolicy Bypass @stageArgs
        if ($LASTEXITCODE -ne 0) {
            throw "stage-oda-resources.ps1 failed with exit code $LASTEXITCODE."
        }
    } else {
        Write-Host "`n[1/4] Skip ODA staging"
        $odaExe = Join-Path $OdaDir "ODAFileConverter.exe"
        $odaQtPlatformPlugin = Join-Path $OdaDir "platforms\qwindows.dll"
        if (-not (Test-Path $odaExe)) {
            Write-Warning "ODA executable not staged at $odaExe. Packaged installs will require a system ODA or ODAFC_PATH."
        } elseif (-not (Test-Path $odaQtPlatformPlugin)) {
            throw "ODA Qt Windows platform plugin missing at $odaQtPlatformPlugin. Re-run without -SkipOda."
        }
    }

    if (-not $SkipSidecar) {
        Write-Host "`n[2/4] Build Python sidecar (PyInstaller one-file)"
        $sidecarArgs = @("-File", (Join-Path $ScriptDir "build-sidecar.ps1"), "-Python", $Python)
        if ($Clean) {
            $sidecarArgs += "-Clean"
        }
        & powershell -NoProfile -ExecutionPolicy Bypass @sidecarArgs
        if ($LASTEXITCODE -ne 0) {
            throw "build-sidecar.ps1 failed with exit code $LASTEXITCODE."
        }
    } else {
        Write-Host "`n[2/4] Skip sidecar build"
        $sidecarExe = Join-Path $SidecarDir "dwg-audit-sidecar.exe"
        if (-not (Test-Path $sidecarExe)) {
            throw "Sidecar executable missing at $sidecarExe. Re-run without -SkipSidecar."
        }
    }

    if (-not $SkipFrontend) {
        Write-Host "`n[3/4] Install frontend deps (if needed) and typecheck/build"
        if (-not (Test-Path (Join-Path $DesktopDir "node_modules"))) {
            & npm install
            if ($LASTEXITCODE -ne 0) {
                throw "npm install failed with exit code $LASTEXITCODE."
            }
        }
        & npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "npm run build failed with exit code $LASTEXITCODE."
        }
    } else {
        Write-Host "`n[3/4] Skip frontend build"
    }

    Write-Host "`n[4/4] Tauri NSIS installer build"
    & npm run tauri:build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run tauri:build failed with exit code $LASTEXITCODE."
    }

    $bundleRoot = Join-Path $TauriDir "target\release\bundle"
    Write-Host "`nRelease artifacts under: $bundleRoot"
    if (Test-Path $bundleRoot) {
        Get-ChildItem -Path $bundleRoot -Recurse -Include *.exe,*.msi,*.nsis.zip -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Host " - $($_.FullName)" }
    }

    $sidecarExe = Join-Path $SidecarDir "dwg-audit-sidecar.exe"
    $odaExe = Join-Path $OdaDir "ODAFileConverter.exe"
    $odaQtPlatformPlugin = Join-Path $OdaDir "platforms\qwindows.dll"
    Write-Host "`nPackaged resource checklist:"
    Write-Host (" - sidecar: {0}" -f ($(if (Test-Path $sidecarExe) { "OK  $sidecarExe" } else { "MISSING" })))
    Write-Host (" - oda:     {0}" -f ($(if (Test-Path $odaExe) { "OK  $odaExe" } else { "MISSING (system ODA fallback only)" })))
    Write-Host (" - oda Qt:  {0}" -f ($(if (Test-Path $odaQtPlatformPlugin) { "OK  $odaQtPlatformPlugin" } else { "MISSING" })))
    Write-Host "`nWindows release build finished."
}
finally {
    Pop-Location
}
