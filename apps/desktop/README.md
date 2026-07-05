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

This machine does not currently have the Rust toolchain installed, so native Tauri execution still cannot be validated here end-to-end.

Once Rust is installed, the intended commands are:

```bash
npm run tauri:dev
npm run tauri:build
```

## Current limitations

- The frontend build is validated (`npm run build`), but Rust/Tauri compilation is still unverified on this machine because `cargo` is unavailable.
- Result review already exposes evidence JSON, one-to-many triage and score breakdown, but richer evidence drawers, multi-reference preview switching and preview regeneration controls still need refinement.
