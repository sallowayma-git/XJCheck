# Windows Offline Packaging Guide

This document describes how to produce a Windows NSIS installer for **DWG Audit Desktop** that embeds:

1. the Tauri desktop shell
2. the Python audit engine as a one-file sidecar (`dwg-audit-sidecar.exe`)
3. ODA File Converter runtime files (`oda/ODAFileConverter.exe` + DLLs)

End-user machines do **not** need Python or ODA preinstalled when both resources are staged before `tauri build`.

## Architecture

```text
Installed app
├── dwg_audit_desktop.exe
├── sidecar/
│   └── dwg-audit-sidecar.exe      # PyInstaller engine
└── oda/
    ├── ODAFileConverter.exe       # DWG -> DXF converter
    └── *.dll / *.tx / Qt runtime
```

### Runtime resolution

**Sidecar**

1. `DWG_AUDIT_SIDECAR_EXE`
2. packaged `sidecar/dwg-audit-sidecar.exe`
3. development fallback: `python -m dwg_audit.cli` (debug only, or `DWG_AUDIT_ALLOW_SOURCE_FALLBACK=1`)

**ODA File Converter**

1. config `ingest.odafc_path` (optional override)
2. `ODAFC_PATH` / `ODA_FILE_CONVERTER` (desktop shell injects bundled path)
3. packaged resource / sidecar sibling `oda/ODAFileConverter.exe`
4. system `PATH`
5. Windows `Program Files\ODA\ODAFileConverter *`

### ODA worker safety defaults

Every external ODA conversion runs in a one-shot worker process. The parent sidecar
keeps the cache/event/provenance state, while the worker owns only the native ODA call.
The default configuration is:

```yaml
ingest:
  oda_process_isolation: true
  oda_timeout_seconds: 300.0
```

When the timeout expires, the worker and its descendants are terminated before the
next conversion is admitted. Windows workers join a kill-on-close Job Object; source
and frozen workers both use the same `oda-worker` protocol. POSIX workers run in a
private process group, receive TERM/KILL escalation, and watch a supervisor-owned
pipe so a crashed sidecar cannot leave the worker session running. Worker stdout and
stderr are drained continuously with a bounded tail, and request writes are also
deadline-bound. Set
`ingest.oda_process_isolation: false` only for controlled diagnostics; that opt-out
does not provide hard native-process cancellation.

## Build machine prerequisites

| Dependency | Purpose |
|---|---|
| Windows 10/11 x64 | release host |
| Python 3.12+ | engine + PyInstaller |
| `pip install -e .` and `pip install pyinstaller` | package engine |
| Node.js 20+ / npm | desktop frontend |
| Rust stable + VS Build Tools (C++/MSVC) | Tauri native build |
| ODA File Converter install | stage source for `resources/oda` |

Notes:

- ODA binaries are **not** committed to git. They are staged locally or restored from a private artifact cache in CI.
- Confirm ODA redistribution rights before shipping a public installer.

## One-command local release

From repository root:

```powershell
cd apps\desktop
npm run package:windows
```

Equivalent:

```powershell
cd apps\desktop
.\scripts\build-windows-release.ps1 -Clean
```

This script:

1. stages ODA into `src-tauri/resources/oda`
2. builds `src-tauri/resources/sidecar/dwg-audit-sidecar.exe`
3. builds the frontend
4. runs `tauri build` (NSIS)

## Step-by-step local release

```powershell
cd apps\desktop

# 1) Stage ODA from a local install or ODAFC_PATH
.\scripts\stage-oda-resources.ps1 -Clean
# or:
# .\scripts\stage-oda-resources.ps1 -SourceDir "C:\Program Files\ODA\ODAFileConverter 27.1.0" -Clean

# 2) Build Python sidecar
.\scripts\build-sidecar.ps1 -Clean

# 3) Build installer
npm run tauri:build
```

## Output artifacts

| Artifact | Typical path |
|---|---|
| Portable/shell exe | `apps/desktop/src-tauri/target/release/dwg_audit_desktop.exe` |
| NSIS installer | `apps/desktop/src-tauri/target/release/bundle/nsis/DWG Audit Desktop_*_x64-setup.exe` |
| Staged sidecar | `apps/desktop/src-tauri/resources/sidecar/dwg-audit-sidecar.exe` |
| Staged ODA | `apps/desktop/src-tauri/resources/oda/ODAFileConverter.exe` |

Expected release resource layout after a successful build:

```text
apps/desktop/src-tauri/target/release/
  dwg_audit_desktop.exe
  sidecar/dwg-audit-sidecar.exe
  oda/ODAFileConverter.exe
  bundle/nsis/DWG Audit Desktop_*_x64-setup.exe
```

## Verification checklist

```powershell
# packaging contract tests
python -m pytest -q tests/unit/test_desktop_packaging.py tests/unit/test_readers.py

# sidecar CLI smoke
.\apps\desktop\src-tauri\resources\sidecar\dwg-audit-sidecar.exe --help

# frozen ODA worker protocol smoke (the build script runs this automatically)
'{"operation":"unsupported-test-operation"}' |
  .\apps\desktop\src-tauri\resources\sidecar\dwg-audit-sidecar.exe oda-worker

# resource presence
Test-Path .\apps\desktop\src-tauri\resources\sidecar\dwg-audit-sidecar.exe
Test-Path .\apps\desktop\src-tauri\resources\oda\ODAFileConverter.exe
Test-Path .\apps\desktop\src-tauri\target\release\bundle\nsis\*.exe
```

Recommended clean-machine smoke:

1. Install the NSIS package on a profile/VM without Python/ODA.
2. Launch the app and import a small DWG project.
3. Confirm conversion + analysis complete without missing-sidecar / missing-ODA errors.

## CI model

Repository workflow: `.github/workflows/windows-package.yml`

### Triggers (release-only)

The packaging workflow does **not** run on ordinary branch pushes or pull requests.

It starts only when:

1. a version tag is pushed: `v*` (example: `v0.1.0`)
2. a GitHub Release is published/edited
3. a manual **workflow_dispatch** dry-run is requested

Recommended release flow:

```powershell
# 1) local verification first
cd apps\desktop
npm run package:windows

# 2) tag + push (CI starts)
git tag v0.1.0
git push origin v0.1.0

# 3) optional: create/publish GitHub Release for that tag
gh release create v0.1.0 --generate-notes
```

### What CI does on tag/release

- checkout the tagged commit
- set up Python / Node / Rust
- install Python package + PyInstaller
- install desktop npm deps
- run packaging unit tests
- restore ODA from Actions cache key `oda-file-converter-windows-v1`
- if ODA is available:
  - build sidecar
  - build frontend
  - build Tauri NSIS installer
  - upload workflow artifact
  - attach installer to the GitHub Release for that tag
- if ODA is missing:
  - contract tests still run
  - installer build is skipped with a clear summary note

### Why ODA is optional in CI

ODA is a third-party binary tree (~70MB) and is gitignored. CI restores it from the GitHub Actions cache key `oda-file-converter-windows-v1` when present.

To seed the cache on a self-hosted or privileged runner:

1. Install ODA File Converter on the runner, or place a prepared tree under a known path.
2. Run `apps/desktop/scripts/stage-oda-resources.ps1`.
3. Manually run **Windows Offline Package** once so the ODA path is cached.

If ODA is not cached:

- packaging unit tests still run
- full installer build is skipped with a clear summary note
- no incomplete public installer is published

### Manual CI trigger

GitHub Actions → **Windows Offline Package** → **Run workflow**.

Optional inputs:

- `build_installer=true|false`
- `force_skip_oda=true` (contract-only mode)
- `upload_release_assets=true` (attach installer to an existing tag release during dry-run)


## Installer size reduction (Phase 170)

Baseline (pre-slim):

| Component | Size |
|---|---|
| NSIS installer | ~113 MB |
| Sidecar one-file | ~92 MB |
| ODA staged tree | ~70 MB |
| Desktop shell | ~9.5 MB |

Current measured (local rebuild after slim scripts):

| Component | Size |
|---|---|
| NSIS installer | ~85 MB → **~68 MB** (after unused-module prune) |
| Sidecar one-file | ~69 MB → **~52 MB** |
| ODA staged tree | ~51 MB |
| Desktop shell | ~9.4 MB |

### Sidecar slim strategy

`apps/desktop/scripts/build-sidecar.ps1` delegates to
`apps/desktop/scripts/build_sidecar_pyinstaller.py`, which:

- does **not** use `--collect-all` (that previously pulled full PyArrow stacks)
- excludes Streamlit / matplotlib / notebook tooling
- drops optional PyArrow natives: flight, substrait, dataset, orc, acero, cloud FS helpers
- keeps core `arrow.dll` + `parquet.dll` + OpenBLAS for pandas artifact I/O
- prunes most `tzdata` zoneinfo continents from the bundle

### ODA slim strategy

`apps/desktop/scripts/stage-oda-resources.ps1` stages the ODA install tree, then
removes a validated optional set (BREP/ACIS helpers, Qt `imageformats`, W3D/Whip
viewer libs, unused `.tx` modules, etc.). Conversion-critical modules such as
`RecomputeDimBlock_27.1_16.tx` are **not** pruned.

Validate any further ODA removals with real DWG conversion via `ezdxf.addons.odafc`
before shipping.


### Unused / never-called dependency pruning

Static reachability from `dwg_audit.desktop.sidecar_entry` plus call-site audit showed:

| Package | Why it was in the bundle | Action |
|---|---|---|
| `networkx` | declared in `pyproject.toml` but **zero imports** in `src/` | exclude |
| `PIL` / `Pillow` | optional `ezdxf.addons.drawing` image export | exclude |
| `jinja2` / `lxml` / `xlsxwriter` | optional pandas Styler / openpyxl backends | exclude |
| `setuptools` / `requests` | transitive tooling | exclude |
| `streamlit` | only `serve-ui` | exclude |
| `fontTools` | required by `ezdxf.fonts` at import time | **keep** |
| `rich` + `pygments` | required by Typer help/error formatting | **keep** |
| pyarrow `include/` / `.lib` / `.pyx` / `src/` | C++ headers & cython sources not needed at runtime | drop as DATA |

Do **not** exclude `pandas.testing` (pandas `__init__` imports it eagerly) or `unittest` (pyparsing.testing).

### Remaining size headroom

Largest remaining sidecar natives: `arrow.dll` (~21 MB), OpenBLAS (~19 MB),
`arrow_compute.dll` (~9 MB), `parquet.dll` (~7 MB). Further cuts need engine-level
dependency changes (e.g. optional parquet backend or lighter numeric stack) and
are outside the packaging-script loop.

## Scripts reference

| Script | Role |
|---|---|
| `apps/desktop/scripts/stage-oda-resources.ps1` | stage ODA install tree + prune optional payloads |
| `apps/desktop/scripts/build-sidecar.ps1` | orchestrates slim PyInstaller sidecar build |
| `apps/desktop/scripts/build_sidecar_pyinstaller.py` | filtered Analysis (drop flight/streamlit/tzdata bloat) |
| `apps/desktop/scripts/build-windows-release.ps1` | full local release orchestration |

npm aliases in `apps/desktop/package.json`:

- `npm run stage:oda`
- `npm run build:sidecar`
- `npm run package:windows`
- `npm run tauri:build`

## Git policy

Tracked:

- packaging scripts
- `apps/desktop/src-tauri/resources/sidecar/README.md`
- `apps/desktop/src-tauri/resources/oda/README.md`
- Tauri config / Rust runtime resolver / Python discovery code
- packaging unit tests

Not tracked (gitignored):

- `resources/sidecar/dwg-audit-sidecar*`
- `resources/oda/**` binaries / markers
- `src-tauri/target/**`
- `node_modules/**`

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Installer build says sidecar missing | skipped PyInstaller step | run `build-sidecar.ps1` |
| Runtime cannot convert DWG | ODA not staged / not injected | stage ODA; confirm `resources/oda/ODAFileConverter.exe` |
| Dev mode falls back to source Python | expected in debug | release uses packaged sidecar only |
| NSIS download timeout | bundler network | pre-warm Tauri NSIS cache, retry |
| CI skips installer | ODA cache miss | seed ODA cache or build locally |

## Related files

- `apps/desktop/README.md` — desktop app overview
- `apps/desktop/src-tauri/tauri.conf.json` — resource mapping
- `apps/desktop/src-tauri/src/sidecar_runtime.rs` — runtime env injection
- `src/dwg_audit/readers/oda_reader.py` — ODA discovery order
- `tests/unit/test_desktop_packaging.py` — packaging contract tests
