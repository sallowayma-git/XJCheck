param(
    [string]$Python = "python",
    [string]$OutputDir = "",
    [switch]$Clean,
    [ValidateSet("onefile", "onedir")]
    [string]$Mode = "onefile"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopDir = Resolve-Path (Join-Path $ScriptDir "..")
$RepoRoot = Resolve-Path (Join-Path $DesktopDir "..\..")
$EntryPoint = Join-Path $RepoRoot "src\dwg_audit\desktop\sidecar_entry.py"
$Builder = Join-Path $ScriptDir "build_sidecar_pyinstaller.py"

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
if (-not (Test-Path $Builder)) {
    throw "Sidecar PyInstaller builder not found: $Builder"
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
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $OutputDir "dwg-audit-sidecar")
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $BuildDir
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $SpecDir
    New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
    New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null
}

# Size-first packaging:
# - filtered Analysis via build_sidecar_pyinstaller.py (no --collect-all)
# - drops optional PyArrow flight/compute/dataset stacks + Streamlit/tzdata bloat
# - keeps parquet/core pyarrow for pandas artifact I/O
& $Python $Builder `
    --entry $EntryPoint `
    --distpath $OutputDir `
    --workpath $BuildDir `
    --specpath $SpecDir `
    --paths (Join-Path $RepoRoot "src") `
    --name "dwg-audit-sidecar" `
    --mode $Mode `
    --python $Python

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed while building dwg-audit-sidecar."
}

$ExePath = Join-Path $OutputDir "dwg-audit-sidecar.exe"
if ($Mode -eq "onedir") {
    $ExePath = Join-Path $OutputDir "dwg-audit-sidecar\dwg-audit-sidecar.exe"
}
if (-not (Test-Path $ExePath)) {
    throw "Expected sidecar executable was not produced: $ExePath"
}

# Exercise the frozen worker dispatcher immediately after every build. This
# catches stale specs, missing hidden imports, and broken stdout protocol before
# the binary is copied into a release installer.
$SmokeInput = '{"operation":"unsupported-test-operation"}'
$SmokeStart = [System.Diagnostics.ProcessStartInfo]::new()
$SmokeStart.FileName = $ExePath
$SmokeStart.Arguments = "oda-worker"
$SmokeStart.UseShellExecute = $false
$SmokeStart.CreateNoWindow = $true
$SmokeStart.RedirectStandardInput = $true
$SmokeStart.RedirectStandardOutput = $true
$SmokeStart.RedirectStandardError = $true
$SmokeProcess = [System.Diagnostics.Process]::new()
$SmokeProcess.StartInfo = $SmokeStart
if (-not $SmokeProcess.Start()) {
    throw "Frozen sidecar ODA worker smoke could not start."
}
$SmokeProcess.StandardInput.WriteLine($SmokeInput)
$SmokeProcess.StandardInput.Close()
if (-not $SmokeProcess.WaitForExit(15000)) {
    try { $SmokeProcess.Kill() } catch {}
    $SmokeProcess.WaitForExit(2000) | Out-Null
    throw "Frozen sidecar ODA worker smoke timed out after 15 seconds."
}
$SmokeRaw = $SmokeProcess.StandardOutput.ReadToEnd()
$SmokeError = $SmokeProcess.StandardError.ReadToEnd()
$SmokeExit = $SmokeProcess.ExitCode
try {
    $Smoke = ($SmokeRaw | Out-String).Trim() | ConvertFrom-Json
} catch {
    throw "Frozen sidecar ODA worker smoke returned non-JSON output: $SmokeRaw $SmokeError"
}
if ($SmokeExit -ne 1 -or $Smoke.error_code -ne "ODA_WORKER_PROTOCOL") {
    throw "Frozen sidecar ODA worker smoke failed: $($Smoke | ConvertTo-Json -Compress)"
}

$Marker = Join-Path $OutputDir "SIDECAR_BUILT_FROM.txt"
@(
    "entrypoint=$EntryPoint"
    "built_at=$((Get-Date).ToString('o'))"
    "python=$Python"
    "mode=$Mode"
    "size_bytes=$((Get-Item $ExePath).Length)"
    "builder=$Builder"
) | Set-Content -Path $Marker -Encoding UTF8

Write-Host "Built sidecar executable: $ExePath"
Write-Host ("Sidecar size: {0:N1} MB" -f (((Get-Item $ExePath).Length) / 1MB))
