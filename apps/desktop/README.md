# DWG Audit Desktop

Tauri 2 + React + TypeScript desktop-shell scaffold for the local DWG audit workflow.

## Included in this scaffold

- Launch surface with recent projects, input directory field and start-analysis action.
- Process surface with stage progress, streamed event log and live issue table.
- Result surface with issue board, issue detail, evidence panel and preview area.
- Sidecar adapter layer that reserves calls to:
  - `analyze-session`
  - `list-recent-projects`
  - `load-result`
  - `render-preview`
- `src-tauri/` bootstrap files for a future native shell.

## Frontend commands

```bash
npm install
npm run dev
npm run build
npm run check
```

## Tauri note

This machine does not currently have the Rust toolchain installed, so native Tauri execution cannot be validated here yet.

Once Rust is installed, the intended commands are:

```bash
npm run tauri:dev
npm run tauri:build
```

## Current limitations

- The sidecar adapter falls back to mocked data when native Tauri commands are not wired yet.
- Directory selection, process streaming and preview loading already have interface placeholders, but they still need the final Rust bridge.
- SQLite-backed recent project data already exists in the Python sidecar; this shell still needs the native bridge to consume it live.
