# Phase 3b.1 Performance Correctness Fix

## Goal
Fix the reviewed ODA lifecycle, run identity, pagination consistency, desktop
settings, project-load cancellation, and virtual-row correctness issues. Commit
only this scoped work while preserving unrelated user changes.

## Phases
- [x] Confirm dirty-worktree and affected-file boundaries.
- [x] Design the minimal cross-language contracts with independent review.
- [x] Fix ODA process ownership, cancellation, and startup resource admission.
- [x] Fix immutable run selection and snapshot-consistent paged reads.
- [x] Fix settings round-trip, reset semantics, and remove or implement no-op controls.
- [x] Make result loading cancelable and use summary/page/detail APIs without UX-blocking pagination.
- [x] Fix virtual row sizing and accessibility behavior.
- [x] Run Python, Node, TypeScript, lint, build, and Rust verification.
- [x] Stage only Phase 3b.1 files and create one local commit.
- [x] Fix post-commit review findings in sidecar fallback, cancellation, paging, and preview identity.
- [x] Re-run targeted/full verification and create a scoped follow-up commit.

## Status
complete

## Guardrails
- Do not modify or stage root task_plan.md, findings.md, progress.md.
- Do not modify or stage src/dwg_audit/audit/rules.py or tests/unit/test_pairs_and_rules.py.
- Do not stage the untracked root package-lock.json.
- Keep legacy load-result behavior available while migrating the desktop UI.

## Errors Encountered
- Initial ODA focused tests hit an AttributeError because the new Windows Job
  cleanup branch used an `else` attached to `if not job_closed`; fixed by making
  the POSIX branch explicitly `os.name != "nt"`.
- Independent review after commit `7ccf3a7` found the source-development
  fallback still invokes `dwg_audit.cli`, which does not expose lightweight
  result commands; use the desktop sidecar entrypoint instead.
- The bundled `rg.exe` returned Windows `Access denied` during post-review code
  inspection; switched subsequent searches to PowerShell `Select-String`.
- The first monolithic state-store patch failed context verification at
  `load_project_issues_page` and made no changes; split it into small,
  independently verifiable patches.
- A subsequent read-only PowerShell spawn returned Windows error 5 from the
  sandbox runner; no source command ran, so later checks use smaller invocations.
- Rust check initially failed because `windows-sys 0.61` does not export
  `Foundation::SYNCHRONIZE`; the result process guard only needs the existing
  `PROCESS_TERMINATE` access right, so the import was removed.
- The desktop package has no `npm test` script; the attempted command returned
  `Missing script: test` without running tests. Use its explicit Node test
  runner instead.
- `cargo fmt --check` reported formatting-only differences in the new result
  state and tests; resolved with `cargo fmt` before final verification.
- A state-store regression proxy replaced `_connect` without the new handling
  UDF and exposed `no such function: dwg_issue_handling_class`; registration
  is now made idempotent at each SQL helper entry as well as connection setup.
