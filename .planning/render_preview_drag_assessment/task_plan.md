# Result Preview Drag Assessment

## Goal
Implement a wider, downward-biased result preview and a bounded draggable viewport: render roughly 1.8-2.3x surrounding context once in the backend, then pan it in the fixed React inspector using Pointer Events, pointer capture, and CSS transforms.

## Scope
- Expand the backend issue focus extent and preserve nearby device/connection geometry.
- Add bounded front-end dragging with automatic reset when preview context changes.
- Preserve the static-SVG/one-sidecar-per-preview architecture; never rerender during pointer movement.
- Add targeted backend and front-end tests; preserve unrelated worktree changes.

## Phases
| Phase | Status | Output |
|---|---|---|
| Reconfirm exact backend/frontend edit surfaces | complete | Current functions, state, CSS, and tests to change |
| Implement 1.8-2.3x downward-biased backend context | complete | Expanded focus extent and metadata/tests |
| Implement bounded Pointer Events dragging | complete | Pointer capture, transform clamping, context reset, mouse/touch/keyboard support, CSS |
| Verify behavior and regression safety | complete | 1329 Python tests, 20 frontend tests, typecheck/lint/build, diff check |

## Errors Encountered
| Error | Attempt | Resolution |
|---|---|---|
| Default subagent spawn inherited unsupported `ultra` reasoning for the locked model | 1 | Retry with the role's documented default `low` reasoning explicitly set |
| Bundled `rg.exe` could not start (`Access denied`) | 1 | Use native PowerShell `Get-ChildItem` / `Select-String` for local verification; do not retry the same binary |
| Parallel PowerShell verification failed to spawn one child (`CreateProcessAsUserW error 5`) | 1 | Retry the two small reads sequentially with simpler commands |
| Later simple PowerShell snippet read also hit `CreateProcessAsUserW error 5` | 1 | Stop retrying the environment-level spawn failure; rely on already verified lines and independent history audit |
| Combined full-file read of preview/state store was truncated | 1 | Read only the exact method/schema chunks to be modified in smaller calls |
| Backend regression run: 2 failures | 1 | Artifact metadata loss was caused by treating an artifact-loaded issue as SQLite-lightweight; gate fallback on `sqlite_issue`. The other failure is an expected assertion update for the new block frame. |
| Combined backend test patch did not match current fixture context | 1 | Split into small, exact patches using the already-read line anchors |
| Front-end helper test returned `-0` for a zero-overflow Y clamp | 1 | Canonicalize zero-bound axes to numeric `0`; typecheck and lint already pass |
| Sidecar integration assertion expected geometry from a fixture with no geometry Parquet frames | 1 | Remove the invalid fixture assumption; persistence/rendering is covered with explicit geometry payload tests |
| Independent review found `list_issue_summaries_page` return displaced by method insertion | 1 | Restore return before new methods and remove unreachable block; run broader state-store/sidecar tests |
| Combined planning update missed the current phase-table context | 1 | Apply smaller exact planning-file patches |
