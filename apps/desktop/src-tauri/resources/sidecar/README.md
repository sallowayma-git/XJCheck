# DWG Audit Sidecar Resource

Run `apps/desktop/scripts/build-sidecar.ps1` before a release bundle to place
`dwg-audit-sidecar.exe` in this directory. Tauri maps this directory into the
app resource root as `sidecar/`, where the Rust command bridge resolves it.
