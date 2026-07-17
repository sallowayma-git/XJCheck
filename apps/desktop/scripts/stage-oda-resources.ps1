param(
    [string]$SourceDir = "",
    [string]$OutputDir = "",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopDir = Resolve-Path (Join-Path $ScriptDir "..")
$RepoRoot = Resolve-Path (Join-Path $DesktopDir "..\..")

if (-not $OutputDir) {
    $OutputDir = Join-Path $DesktopDir "src-tauri\resources\oda"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)

function Resolve-DefaultOdaSource {
    $candidates = @()
    foreach ($variable in @("ODAFC_PATH", "ODA_FILE_CONVERTER", "DWG_AUDIT_BUNDLED_ODA_DIR")) {
        $raw = [Environment]::GetEnvironmentVariable($variable)
        if (-not [string]::IsNullOrWhiteSpace($raw)) {
            $path = [System.IO.Path]::GetFullPath($raw)
            if (Test-Path $path -PathType Leaf) {
                $candidates += (Split-Path -Parent $path)
            } elseif (Test-Path $path -PathType Container) {
                $candidates += $path
            }
        }
    }

    foreach ($root in @(
        ${env:ProgramFiles},
        ${env:ProgramW6432},
        ${env:ProgramFiles(x86)}
    )) {
        if ([string]::IsNullOrWhiteSpace($root)) {
            continue
        }
        $odaRoot = Join-Path $root "ODA"
        if (-not (Test-Path $odaRoot)) {
            continue
        }
        $matches = Get-ChildItem -Path $odaRoot -Directory -Filter "ODAFileConverter*" -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending
        foreach ($match in $matches) {
            $exe = Join-Path $match.FullName "ODAFileConverter.exe"
            if (Test-Path $exe) {
                $candidates += $match.FullName
            }
        }
    }

    foreach ($candidate in $candidates) {
        $exe = Join-Path $candidate "ODAFileConverter.exe"
        if (Test-Path $exe) {
            return $candidate
        }
    }
    return $null
}

if (-not $SourceDir) {
    $SourceDir = Resolve-DefaultOdaSource
}
if (-not $SourceDir) {
    throw "ODA File Converter source directory was not found. Pass -SourceDir or install ODA File Converter / set ODAFC_PATH."
}
$SourceDir = [System.IO.Path]::GetFullPath($SourceDir)
$SourceExe = Join-Path $SourceDir "ODAFileConverter.exe"
if (-not (Test-Path $SourceExe)) {
    throw "Source directory does not contain ODAFileConverter.exe: $SourceDir"
}

if ($Clean -and (Test-Path $OutputDir)) {
    # Keep tracked documentation while removing staged binaries.
    Get-ChildItem -Path $OutputDir -Force |
        Where-Object { $_.Name -ne "README.md" } |
        Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

# Ensure README remains present even if the directory was empty.
$ReadmePath = Join-Path $OutputDir "README.md"
if (-not (Test-Path $ReadmePath)) {
    @(
        "# Bundled ODA File Converter resources"
        ""
        "Stage binaries with ``apps/desktop/scripts/stage-oda-resources.ps1``."
        "Do not commit ODA binaries to git."
    ) | Set-Content -Path $ReadmePath -Encoding UTF8
}

Write-Host "Staging ODA File Converter from: $SourceDir"
Write-Host "Destination: $OutputDir"

$robocopy = Get-Command robocopy -ErrorAction SilentlyContinue
if ($robocopy) {
    & robocopy $SourceDir $OutputDir /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed while staging ODA resources (exit $LASTEXITCODE)."
    }
} else {
    Copy-Item -Path (Join-Path $SourceDir "*") -Destination $OutputDir -Recurse -Force
}

$StagedExe = Join-Path $OutputDir "ODAFileConverter.exe"
if (-not (Test-Path $StagedExe)) {
    throw "Expected staged executable was not produced: $StagedExe"
}

# Marker used by packaging tests / release scripts; never commit binary payloads.
$Marker = Join-Path $OutputDir "PACKAGED_FROM.txt"
@(
    "source=$SourceDir"
    "staged_at=$((Get-Date).ToString('o'))"
    "machine=$env:COMPUTERNAME"
) | Set-Content -Path $Marker -Encoding UTF8


# Optional payload prune: keep DWG->DXF conversion working while dropping
# BREP/ACIS/viewer extras that are not required by ezdxf odafc conversion.
$OptionalRemovals = @(
    "imageformats",
    "Icon-ODA.ico",
    "W3Dtk.dll",
    "WhipTk.dll",
    "OdBrepModeler_27.1_16.dll",
    "OdHlrAlgoBrep_27.1_16.dll",
    "TD_BrepRenderer_27.1_16.dll",
    "TD_BrepBuilder_27.1_16.dll",
    "TD_BrepBuilderFiller_27.1_16.dll",
    "TD_AcisBuilder_27.1_16.dll",
    "ModelerGeometry_27.1_16.tx",
    "DbProperties_27.1_16.tx",
    "AcTrace_27.1_16.tx",
    "AcSynergyObjDPW_27.1_16.tx",
    "AcModelDocObj_27.1_16.tx",
    "ExFieldEvaluator_27.1_16.tx",
    "RxCommonDataAccess_27.1_16.tx",
    "RxProperties_27.1_16.tx",
    "libcrypto_27.1_16.dll"
)

$removed = @()
foreach ($name in $OptionalRemovals) {
    $target = Join-Path $OutputDir $name
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
        $removed += $name
    }
}

$stagedBytes = (Get-ChildItem -Path $OutputDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$stagedMb = [math]::Round(($stagedBytes / 1MB), 1)
Write-Host ("Pruned optional ODA payloads: {0}" -f ($(if ($removed.Count) { ($removed -join ', ') } else { '(none)' })))
Write-Host ("Staged ODA size: {0} MB" -f $stagedMb)

Write-Host "Staged ODA File Converter: $StagedExe"
