---
title: "Stop physical folder moves on PR-only main in finalize Step 6c"
status: todo
components:
  - ticket_lifecycle
  - build_pipeline
created: 2026-06-24
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 04: Stop physical folder moves on PR-only main in finalize Step 6c

## Actor / Goal

In order to stop finalize from creating local-only commits that can never reach
origin, we need Step 6c to stop physically `git mv`-ing ticket files on `main`
and instead rely on frontmatter `status:` as the source of truth — so the ticket
lifecycle stays consistent between local and origin.

## Context

This is a P0 defect that the manual finalize of PR #152 **reproduced live**.
Step 6c (`finalize-feature.js`, roughly lines 768-823) does `git mv`
(inbox→`99_done`) + `git commit` on local `main`, but never pushes. `main` is
PR-only (ruff branch protection rejects a direct push: `GH013 ... Required status
check "Lint (ruff)"`). So the reconciliation commit:

- stays local-only and diverges from `origin/main`,
- is dropped/overwritten on the next `git pull` / reset,
- leaves the ticket file in `00_inbox/` on origin forever even though its
  frontmatter says `status: done`.

The EPIC-MoveOnMainOnly tickets already show duplicate inbox+done copies on origin
caused by this exact mechanism — the corruption that epic was built to prevent,
reproduced by the finalize flow itself.

The rest of the stack already treats `status:` as authoritative and ignores
folder position (`ticket-prioritizer`, `finalize-feature-archive-check`,
`ticket_lifecycle` — BO-400a-3/4/5, BO-400c-1/2). So the physical move is now
redundant AND unmergeable. Preferred fix: retire Step 6c's move+commit entirely
and let `status:` drive everything. (Confirm EPIC-MoveOnMainOnly's intent in its
Master_Plan / tickets before finalizing the approach — this ticket extends "branches
don't move files" to "main doesn't move files either".)

## Acceptance Criteria

- [ ] AC-1: Finalize no longer performs `git mv` of ticket files on `main`, and
  no longer creates a `chore(tickets): reconcile folder positions after merge`
  commit on `main`.
- [ ] AC-2: After a finalize run, local `main` has no commits that are absent from
  `origin/main` as a result of folder reconciliation (no local-only divergence).
- [ ] AC-3: Ticket closure is driven solely by frontmatter `status: done`
  (already set on the merged branch); the prioritizer/archive-check continue to
  report the ticket as done regardless of its physical folder.
- [ ] AC-4: The step's removal/replacement is reflected in the step map doc
  (`templates/workflows/finalize-feature.md`) so the documented flow matches the
  JS (see also ticket 09's step-number drift item).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Confirm EPIC-MoveOnMainOnly intent; decide retire-vs-PR-reconcile (default: retire).
- [ ] Remove Step 6c's `git mv` + commit from finalize-feature.js.
- [ ] Add a regression test asserting finalize produces no local-only reconciliation commit.
- [ ] Update the step map doc.

## Risk & Safety
- Touches money? No.
- Touches data? Changes ticket-file placement behavior on main, but `status:` is
  already the authoritative lifecycle signal — no data loss.
- Reversibility? High.

## Out of Scope
- Cleaning up the pre-existing duplicate inbox/done copies already on origin
  (that is the dormant EPIC-MoveOnMainOnly cleanup tool's job).
