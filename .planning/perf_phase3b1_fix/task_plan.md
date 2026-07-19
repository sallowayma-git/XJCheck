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
- [ ] Run Python, Node, TypeScript, lint, build, and Rust verification.
- [ ] Stage only Phase 3b.1 files and create one local commit.

## Status
in_progress

## Guardrails
- Do not modify or stage root task_plan.md, findings.md, progress.md.
- Do not modify or stage src/dwg_audit/audit/rules.py or tests/unit/test_pairs_and_rules.py.
- Do not stage the untracked root package-lock.json.
- Keep legacy load-result behavior available while migrating the desktop UI.

## Errors Encountered
- Initial ODA focused tests hit an AttributeError because the new Windows Job
  cleanup branch used an `else` attached to `if not job_closed`; fixed by making
  the POSIX branch explicitly `os.name != "nt"`.
