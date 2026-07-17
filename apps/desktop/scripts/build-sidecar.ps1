param(
    [string]$Python = "python",
    [string]$OutputDir = "",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopDir = Resolve-Path (Join-Path $ScriptDir "..")
$RepoRoot = Resolve-Path (Join-Path $DesktopDir "..\..")
$EntryPoint = Join-Path $RepoRoot "src\dwg_audit\desktop\sidecar_entry.py"

if (-not $OutputDir) {
    $OutputDir = Join-Path $DesktopDir "src-tauri\resources\sidecar"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$TmpRoot = Join-Path $RepoRoot ".tmp\desktop_sidecar_pyinstaller"
$BuildDir = Join-Path $TmpRoot "build"
$SpecDir = Join-Path $TmpRoot "spec"

if (-not (Test-Path $EntryPoint)) {
    throw "Sidecar entrypoint not found: $EntryPoint"
}

& $Python -m PyInstaller --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is required. Install it in the packaging environment, then rerun this script."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null

if ($Clean) {
    Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $OutputDir "dwg-audit-sidecar.exe")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $BuildDir
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $SpecDir
    New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
    New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null
}

& $Python -m PyInstaller `
    --onefile `
    --noconfirm `
    --clean `
    --name dwg-audit-sidecar `
    --distpath $OutputDir `
    --workpath $BuildDir `
    --specpath $SpecDir `
    --paths (Join-Path $RepoRoot "src") `
    --collect-all pyarrow `
    --collect-all pandas `
    --collect-all openpyxl `
    --collect-all yaml `
    --hidden-import shapely `
    --hidden-import networkx `
    --hidden-import ezdxf `
    --hidden-import ezdxf.addons.odafc `
    $EntryPoint

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed while building dwg-audit-sidecar."
}

$ExePath = Join-Path $OutputDir "dwg-audit-sidecar.exe"
if (-not (Test-Path $ExePath)) {
    throw "Expected sidecar executable was not produced: $ExePath"
}

# Lightweight packaging marker for release scripts / tests.
$Marker = Join-Path $OutputDir "SIDECAR_BUILT_FROM.txt"
@(
    "entrypoint=$EntryPoint"
    "built_at=$((Get-Date).ToString('o'))"
    "python=$Python"
) | Set-Content -Path $Marker -Encoding UTF8

Write-Host "Built sidecar executable: $ExePath"
