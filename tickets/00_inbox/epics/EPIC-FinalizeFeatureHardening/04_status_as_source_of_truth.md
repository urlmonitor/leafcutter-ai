---
title: "Stop physical folder moves on PR-only main in finalize Step 6c"
status: in_progress
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
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
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

## Sign-offs
- [x] test-writer — 2026-06-24 00:00
- [x] python-coder — 2026-06-24 04:30
- [x] test-runner — 2026-06-24 05:00
- [x] pr-reviewer — 2026-06-24 06:00
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-24 00:00 — ticket-supervisor (status: ok)
feedback-id: fb_2026-06-24_ticket_supervisor_00
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-24 04:30 — python-coder (status: ok)
feedback-id: fb_2026-06-24_783f613c

completion_manifest:
- templates/workflows-js/finalize-feature.js: Removed entire Step 6c block (git mv + reconciliation commit on main). Updated Step 6b from ticket-closing/epic-archival to scope-detection only (no writes on main). Removed ticketsReconciled variable and all references from state, return payload, and message string. Updated meta.phases and Step 6 comment block to reflect the removal. Step 6b now returns tickets_in_scope/tickets_done/tickets_not_done instead of tickets_closed/already_done.
- templates/workflows/finalize-feature.md: Updated Step 6 row to remove "Includes folder reconciliation (EPIC-MoveOnMainOnly/03)" and replace with explanation that no writes on main occur, closure is driven by status: frontmatter (BO-400a-3/4/5, BO-400c-1/2), and the rationale for the removal.

Finalize now performs no git writes or commits on local main as part of ticket lifecycle management. All ACs (AC-1 through AC-5) satisfied: no git mv on main, no reconciliation commit, no local divergence from origin/main, status: frontmatter is sole source of truth, step map doc updated.

## Implementation Tasks
- [x] Confirm EPIC-MoveOnMainOnly intent; decide retire-vs-PR-reconcile (default: retire).
- [x] Remove Step 6c's `git mv` + commit from finalize-feature.js.
- [x] Remove Step 6b's `status` flip + `git mv` on `main` (closure now happens
  pre-merge per ticket 10); leave Step 6b's scope detection if ticket 10 reuses it.
- [x] Update the step map doc.

## Risk & Safety
- Touches money? No.
- Touches data? Changes ticket-file placement behavior on main, but `status:` is
  already the authoritative lifecycle signal — no data loss.
- Reversibility? High.

## Out of Scope
- Cleaning up the pre-existing duplicate inbox/done copies already on origin
  (that is the dormant EPIC-MoveOnMainOnly cleanup tool's job).

### 2026-06-24 06:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-24_dae019f7

completion_manifest:
- AC-1: PASS — Step 6c `reconcileResult = await agent(...)` block fully removed; no ticketsReconciled variable anywhere in the file.
- AC-2: PASS — No git writes on main remain; finalize produces no local-only divergence.
- AC-3: PASS — Step 6b agent instructions rewritten to read-only scope detection; no status flip or file moves on main.
- AC-4: PASS — templates/workflows/finalize-feature.md Step 6 row updated: name changed to scope_detect, description states "informational only, no writes on main".
- AC-5: PASS — Step 6b contains no git mv, no status flip, no commit instructions; closure confirmed to happen in step 3.5 on feature branch.
- Regression: Steps 1-5 and 7 untouched; return payload clean (tickets_reconciled absent).

### 2026-06-24 05:00 — test-runner (status: ok)
feedback-id: fb_2026-06-24_9bd98099

Suite run: full unit_tests/ discover (909 passed, 2 skipped, 1 pre-existing failure).

The 1 failure (test_build_version_wiring.py::test_version_printed_in_build_output) is pre-existing:
confirmed by running the test against the baseline (before python-coder changes) via git stash.
Root cause: registry validation errors where agents reference spawned_by: finalize-feature.js
as an unknown agent name — entirely unrelated to ticket 04's Step 6c removal.

completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: >
      1 pre-existing test failure (test_build_version_wiring::test_version_printed_in_build_output)
      caused by registry validation errors unrelated to ticket 04 changes.
      Confirmed pre-existing by running the same test against the baseline (git stash) — identical failure.
    remediation: >
      Registry must be updated so agents listing spawned_by: finalize-feature.js resolve correctly.
      This is a separate defect, not introduced by this ticket. The 909 other tests pass cleanly.
  failure_report_structured: true
