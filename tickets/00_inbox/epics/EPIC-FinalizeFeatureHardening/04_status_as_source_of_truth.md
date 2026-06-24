---
title: "Stop physical folder moves on PR-only main in finalize Step 6c"
status: todo
components:
  - ticket_lifecycle
  - build_pipeline
created: 2026-06-24
depends_on:
  - 10_close_acs_on_finalize.md
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

**Relationship to ticket 10 (depends_on).** Ticket 10 moves *lifecycle closure*
(ticket `status: done` + source-AC `work_status: done`) to a commit on the
**feature branch before** the PR merge, so the closed state arrives on
`origin/main` via the PR. That is what makes this ticket's AC-3 assumption —
"`status: done` already set on the merged branch" — actually true. Land 10
first; then this ticket removes the now-redundant **main-side** writes: both
Step 6c's reconciliation `git mv`+commit (primary target) and Step 6b's
post-merge `status` flip + move on local `main` (also unpushable). After both,
finalize performs **no writes on `main`** at all.

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
- [ ] AC-5: Step 6b no longer flips `status:` or moves ticket files on local
  `main` either — that closure now happens pre-merge on the feature branch
  (ticket 10). After this ticket, finalize performs no ticket-file writes or
  commits on `main` at all.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

## Implementation Tasks
- [ ] Confirm EPIC-MoveOnMainOnly intent; decide retire-vs-PR-reconcile (default: retire).
- [ ] Remove Step 6c's `git mv` + commit from finalize-feature.js.
- [ ] Remove Step 6b's `status` flip + `git mv` on `main` (closure now happens
  pre-merge per ticket 10); leave Step 6b's scope detection if ticket 10 reuses it.
- [ ] Add a regression test asserting finalize produces no local-only commit
  (reconciliation or status flip) on `main`.
- [ ] Update the step map doc.

## Risk & Safety
- Touches money? No.
- Touches data? Changes ticket-file placement behavior on main, but `status:` is
  already the authoritative lifecycle signal — no data loss.
- Reversibility? High.

## Out of Scope
- Cleaning up the pre-existing duplicate inbox/done copies already on origin
  (that is the dormant EPIC-MoveOnMainOnly cleanup tool's job).
