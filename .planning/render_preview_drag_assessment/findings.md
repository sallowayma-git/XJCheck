# Findings

## Current Rendering Model
- `apps/desktop/src/App.tsx:1210-1251` debounces for 240 ms, calls `desktopApi.renderPreview`, and stores the returned preview source only when the request and generation are still current.
- `apps/desktop/src/App.tsx:2030-2043` displays the preview as a normal `<img>`, not Canvas/WebGL; image load failure clears the source.
- `apps/desktop/src/lib/desktopApi.ts:564-576` prefers an inline `data:image/svg+xml` URL and falls back to a Tauri asset URL for `preview_path` with cache busting.
- `src/dwg_audit/desktop/preview.py:16-24,98-172` builds a static 960x540 SVG, caps visible geometry at 240 lines and 160 texts, writes the SVG into the preview cache, and returns the SVG/path metadata.
- The default cache is `%LOCALAPPDATA%/dwg-audit/preview-cache`; full cleanup removes it, and stale cleanup removes old project entries (`desktop/lifecycle.py:17-19,83-86,127-140`).
- `apps/desktop/src-tauri/src/main.rs:367-405,820-906` starts a `render-preview` sidecar per request inside `spawn_blocking`; cancellation/timeout terminates the child and drains stdout/stderr reader threads.
- Geometry evidence in SQLite uses a lightweight path and avoids multi-megabyte parquet loads; missing geometry can fall back to loading report frames.
- The renderer computes a tight issue focus extent, filters lines/texts to that extent, maps it into the fixed 960x540 canvas, and emits only that cropped content (`preview.py:123-158,402-433`). The delivered SVG does not contain arbitrary neighboring sheet content.

## Visibility Failure Candidates
- The UI exposes `previewSrc` only when `previewOutputContextKey` exactly matches the current project/run/issue/sheet/line-group/revision context (`App.tsx:1071-1089`). A valid render can therefore exist while `visiblePreviewSrc` is null.
- A null session epoch clears the source and prevents a request until registration completes (`App.tsx:1163-1169`).
- Switching context invalidates/cancels in-flight work, so stale responses are intentionally discarded (`App.tsx:1237-1277`).
- An empty normalized payload or inaccessible fallback asset URL reaches `<img onError>`, which clears the image (`App.tsx:2037-2042`; `src/lib/desktopApi.ts:564-576`).
- Layout is unlikely to be the primary zero-size cause: desktop preview has a minimum 170 px grid row / 150 px shell, mobile has a 220 px row, and the image uses `object-fit: contain` (`App.css:783-786,906-934,1369-1371`).
- CSP is not blocking inline SVG: Tauri config uses `security.csp: null`, enables the asset protocol with `scope: ["**"]`, and `index.html` has no meta CSP (`src-tauri/tauri.conf.json:24-31`; `index.html:1-12`).
- The Python renderer/CLI returns `preview_svg` and `preview_path`, not `preview_src` (`preview.py:109-121,160-172`; `cli.py:636-658`). Therefore normal packaged requests should take the inline SVG branch, not accidentally treat a Windows path as an image URL.

## Main-Agent Verification
- Confirmed the effect clears both the prior source and output key before each request (`App.tsx:1204-1208`), waits 240 ms, validates request ownership/current generation, then writes the source and the exact captured context key together (`1237-1250`). The context gate is intentional stale-output protection; it becomes a symptom only if context churn repeatedly invalidates otherwise successful work.
- Confirmed session-not-ready, non-result screen, missing project/issue, and preview policy all explicitly clear the source (`1163-1199`).
- Confirmed `<img onError>` discards both source and output key and turns the failure into the localized user-visible error (`2030-2042`).
- Confirmed payload normalization accepts an existing `preview_src`, otherwise encodes `preview_svg`, otherwise converts `preview_path`; if all are absent, a successful command normalizes to `preview_src: null` without throwing (`src/lib/desktopApi.ts:564-576`).
- Confirmed `withCacheBust` explicitly leaves `data:` URLs unchanged (`src/lib/desktopApi.ts:612-619`), so query-string corruption of inline SVG is not the visibility bug.
- Confirmed Python projects CAD coordinates into 960x540 pixel coordinates before serializing the SVG (`preview.py:175-246,402-421`). The SVG has a fixed `viewBox="0 0 960 540"`; it carries no CAD-world viewport state that the React layer can currently manipulate.
- Confirmed each request is a `spawn_blocking` task around a newly launched sidecar, with separate stdout/stderr drain threads and polling cancellation/timeout (`src-tauri/src/main.rs:367-409,790-893`).
- Confirmed the desktop package has React/Tauri and virtual-list dependencies but no image-viewer/gesture/canvas library (`apps/desktop/package.json`). Pointer-event pan does not require a new dependency.
- Confirmed unit tests explicitly require preview output to be visible only for an exact context-key match (`apps/desktop/tests/previewPolicy.test.mjs:44-56`). This gate is deliberate, not an accidental comparison, though repeated context changes can keep the UI in an empty/loading cycle.
- Existing desktop JS tests exercise preview policy and request generations, but there is no mounted React/WebView test covering whether a real SVG payload reaches and paints in `<img>`.

## Interaction and Resource Implications
- There is no existing pan/drag/zoom handler or dedicated viewer dependency.
- CSS/SVG pan of the already-generated static image would not invoke the sidecar. It adds pointer-event state and ordinary WebView compositing, with low incremental CPU/GPU cost and no extra backend process/IO per frame.
- However, panning the current `<img>` alone is not meaningful navigation: it only moves the complete 960x540 crop and exposes empty viewport space. A useful small-range pan needs one initial SVG containing an expanded/overscanned neighborhood, followed by front-end-only transforms.
- A bounded overscan approach can retain a single sidecar request and the current entity caps. Its one-time SVG size and generation work increase with the chosen neighborhood, while drag frames remain front-end-only.
- For current-crop inspection only, client-side scale + translate can provide zoom/pan without changing the backend. For navigating into adjacent CAD context, the backend must include a larger focus extent in the one SVG response, then the client can scale/translate that static vector.
- Re-rendering on every drag update would repeat sidecar startup, SQLite/parquet reads, SVG serialization, and cache writes; this is the high-cost approach and should be avoided.
- Replacing the design with a persistent Canvas/WebGL renderer would create ongoing scene/buffer/VRAM cost and is unnecessary for simple inspection panning.
- Existing tests cover static preview generation, lightweight data sourcing, metadata, and cache cleanup, but not pointer interactions or render latency.
- Recommended shape: render a bounded 1.5-2x neighborhood once, keep the issue centered, display the vector at a matching client-side scale, and clamp pointer-driven translation inside the preview shell. Reset transform on issue/context changes; do not call `renderPreview` during pointer movement.
- The SVG currently bakes its title/header into the image, so zoom/pan would move that header too. A polished viewer should keep metadata as a fixed React overlay or accept that behavior in the smallest first iteration.

## Verification Results
- `npm run test:requests`: 16/16 desktop helper tests passed, including preview policy, current-context gating, request invalidation, and keyed request ownership.
- `python -m pytest tests/unit/test_desktop_lifecycle.py -k "render_project_preview" -q`: 2/2 targeted SVG generation tests passed.
- These tests prove helper/backend generation behavior, but still do not exercise an SVG data URL painting inside the packaged Tauri WebView.
- No packaged-WebView test exercises actual data-SVG painting, Tauri asset URLs, or `<img onError>`. The packaged app relies on the system WebView2 runtime.
- The current machine has no `%LOCALAPPDATA%/dwg-audit/preview-cache` directory, so there is no retained failing SVG/payload to inspect locally.
- Preview lifecycle code changed in several recent commits, especially `42545a8` (result loading/cancellation) and `20381d7` (conversion/preview lifecycles); history needs a targeted regression check rather than assuming current gate behavior is longstanding.
- Direct source tracing eliminates the raw-path-in-`preview_src` theory for the normal CLI path; remaining likely classes are lifecycle/context churn, an invalid/empty payload on a specific record, or an environment-specific WebView paint/load failure.
- Git history review found no explicit SVG-loss regression. Commit `20381d7` introduced the current generation/context/cancellation model; `42545a8` later strengthened session registration and result-load cancellation.
- Highest-value runtime checks are: session epoch becoming ready after the initial null effect; rapid issue/sheet/line-group switches invalidating a just-finished response; run/sheet ownership validation rejecting a payload; and line-group correction changing the context key during preview startup.

## Final Assessment
- A draggable viewport is feasible with the current static-SVG architecture.
- Front-end-only pan/zoom adds small, bounded compositor and image-surface cost, with zero extra sidecar/process/disk work per drag frame.
- Meaningful adjacent-area navigation needs a modest overscan change in the Python focus extent; moving the current crop alone cannot reveal omitted geometry.
- Drag-triggered backend rerender and a persistent WebGL scene are both disproportionate to this requirement and should be avoided.
- Fix/observe the current visibility lifecycle before adding gestures so an interaction change does not mask the existing failure.

## Implementation Direction Confirmed by User
- The core complaint is insufficient/upper-biased framing: numeric evidence appears, but the device and connected area below are missing.
- Backend target: include roughly 1.8-2.3x surrounding context and bias the initial field of view downward.
- Frontend target: fixed viewport with Pointer Events, pointer capture, bounded CSS translation, and automatic reset whenever the selected preview context changes.
- Dragging must operate entirely on the already-returned SVG; no sidecar request during pointer movement.

## Implementation Data Constraint
- The current SQLite lightweight path contains only issue/page summaries and evidence JSON. With `line_start`/`line_end`, it synthesizes the issue line and endpoint texts; it has no neighboring device/block/connection entities.
- Nearby `lines`, `texts`, `line_groups`, `blocks`, and `polylines` exist only in per-table Parquet artifacts. Current `load_report_frames` reads each requested table fully, then preview filters in pandas.
- Therefore multiplying the focus bbox alone would still show mostly blank context for lightweight previews. The implementation must either retain/query compact preview geometry or selectively load still-existing artifacts.
- Safe immediate Parquet optimization: project necessary columns and apply optional `sheet_id` filters, then keep exact bbox filtering in pandas. Since files are not partitioned/sorted datasets, row-group I/O savings are not guaranteed, but column-memory savings are reliable.
- Front-end constraint: the current image layout box always equals the shell (`width/height:100%; object-fit:contain`), so bounded pan would compute zero overflow. A separate scaled content layer or explicit rendered content dimensions are required.
- The preview context key already includes revision/run/project/issue/sheet/line-group, so resetting pan on `visiblePreviewSrc`/`previewContextKey` covers all requested selection changes.
- The backend can return a numeric `viewport_scale` (target 2.1) with the SVG. The front end can compute the contained 960x540 size, scale that explicit layer, and clamp translation to half the scaled overflow on each axis.
- Existing Node tests transpile standalone TypeScript helpers, so pan sizing/clamping should live in a dependency-free `src/lib/previewPan.ts` and be tested without mounting React/WebView.
- `App` already keeps request/session refs adjacent to the preview state. Pan state, shell/image refs, and an active pointer drag ref can be added there without touching result-fetch ownership logic.
- Existing backend tests cover artifact rendering, explicit line-group override, cache partitioning, and SQLite-only fallback; new geometry persistence/expanded-framing assertions can extend those fixtures rather than creating a separate harness.
- The preview artifact fixture has one 120x80 page, one y=20 line/text, and one line group. It can be extended with a lower-y wire and block insertion to prove downward context and device markers survive SQLite-only rendering.
- `analyze_session` tests compact by default, so asserting `store.load_preview_geometry(run_id, "S1")` after completion directly verifies geometry persistence survives workspace deletion.
- `_store_project_run` currently persists only pairs/issues/page findings, then `compact_session_workspace` clears `artifact_dir` and deletes the entire session workspace. `analyze_session(..., compact_after_store=True)` defaults compaction on (`desktop/sidecar.py:41-51,87-113,320-360`; `desktop/lifecycle.py:22-42`). Later on-demand previews therefore cannot recover surrounding Parquet geometry in the default path.
- Polyline vertices are already expanded into `LineEntity` segments, and expanded INSERT children carry `source_block_name`; lines/texts therefore contain most drawable wiring/symbol geometry. `BlockRecord` has only insertion point/name/rotation/attributes and no bbox, so a block marker/label is useful when child geometry is absent.
- Recommended persistence is an SQLite table keyed by run and sheet holding compact preview geometry. SQLite is preserved by compaction and participates in purge transactions; the preview-cache directory is explicitly subject to stale/transient deletion and is not reliable as the only semantic source.
- A per-sheet compressed JSON/blob payload with only renderer-required columns avoids repeated full Parquet reads while supporting all issues and alternate preview sheets without per-issue duplication.
- `DesktopStateStore` already uses per-operation SQLite transactions and manual purge ordering. The new table can follow `replace_page_findings`: delete/insert rows for one run, load one `(run_id, sheet_id)` row, and add deletion before runs in both `purge_session` and `purge_project`.
- Schema creation is `CREATE TABLE IF NOT EXISTS` without a versioned migration framework, so adding a new table/index is backward-compatible for existing databases.
