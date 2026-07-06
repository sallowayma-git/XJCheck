# DWG Audit Desktop

Tauri 2 + React + TypeScript desktop-shell scaffold for the local DWG audit workflow.

## Included in this scaffold

- Launch surface with recent projects, manual input, native folder picker, drag-and-drop folder import and start-analysis action.
- Process surface with stage progress, streamed event log and live issue table.
- Result surface with issue board, issue detail, evidence panel and preview area.
- Sidecar adapter layer that now targets native calls for:
  - `analyze-session`
  - `list-recent-projects`
  - `load-result`
  - `render-preview`
  - `set-issue-status`
- `src-tauri/` command bridge that shells out to the existing Python CLI / sidecar and re-emits JSONL runtime events to the frontend.

## Frontend commands

```bash
npm install
npm run dev
npm run build
npm run check
```

## Tauri note

The Tauri command bridge resolves the DWG audit runtime in this order:

1. `DWG_AUDIT_SIDECAR_EXE`, pointing at a packaged `dwg-audit-sidecar` executable.
2. A bundled app resource named `dwg-audit-sidecar.exe`, `dwg-audit-sidecar`, `sidecar/dwg-audit-sidecar.exe`, or `sidecar/dwg-audit-sidecar`.
3. Development-only source fallback through `python -m dwg_audit.cli`.

Release builds must use a packaged sidecar executable or `DWG_AUDIT_SIDECAR_EXE`. The source checkout fallback is available in debug builds and can be forced with `DWG_AUDIT_ALLOW_SOURCE_FALLBACK=1` for local diagnostics.

Useful native commands:

```bash
npm run tauri:dev
npm run tauri:build
```

## Current limitations

- The shell now has an explicit sidecar runtime contract, but the actual packaged `dwg-audit-sidecar` binary still needs to be produced and bundled before the installer is source-tree independent.
- Result review already exposes evidence JSON, one-to-many triage and score breakdown, but richer evidence drawers, multi-reference preview switching and preview regeneration controls still need refinement.
