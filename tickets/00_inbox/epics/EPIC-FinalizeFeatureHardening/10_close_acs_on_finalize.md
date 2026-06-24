---
title: "Close tickets and source ACs on the feature branch BEFORE the PR merge"
status: in_progress
components:
  - ac_store
  - build_pipeline
  - ticket_lifecycle
created: 2026-06-24
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/finalize-feature.md
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 10: Close tickets and source ACs on the feature branch BEFORE the PR merge

## Actor / Goal

In order to close the AC-first build loop without a second PR, we need
`/finalize-feature` to mark each shipped ticket `status: done` **and** its
`source_ac` `work_status: done` on the **feature branch, before the PR merges**
— so the closure commit rides the PR onto `origin/main` atomically, instead of
being written on local `main` (PR-only) where it can never reach origin.

## Context

`main` is PR-only (ruff branch protection rejects a direct push). Any commit
finalize makes on local `main` is therefore stranded: lost on the next pull, or
requiring a second PR just to record closure. The current finalize ordering
trips on exactly this:

1. Step 4 — `gh pr merge` lands the PR (ticket still `status: todo`) on origin/main.
2. Step 5 — `git checkout main && git pull`.
3. Step 6 — flips ticket `status:` → done **on local main** (Step 6b/6c) — unpushable.

So the lifecycle close is either dropped or needs another PR. The same defect
applies to AC closure: AC YAML files are tracked, so flipping `work_status: done`
after the merge is equally unpushable.

**The fix is an ordering change, not a new post-merge step.** Do all lifecycle
closure on the **feature branch**, after the test+triage gate passes (Step 3)
and before the PR merge (Step 4), in a single commit that the PR carries to
origin/main. After this lands:

- ticket `status: todo → done` is set pre-merge, so it arrives on origin/main
  with the merge — no main-side write needed.
- `source_ac` `work_status: todo → done` is set in the same commit, closing the
  AC-first loop so `scan_ac_store.py` (which filters to `work_status: todo`)
  stops re-proposing already-shipped ACs.

This ticket **supersedes** the post-merge "sub-step 6d" approach from the prior
draft of this ticket, which had the same unpushable-local-main bug it was meant
to fix.

### Existing machinery to reuse

- `scripts/ac_store/mark_ac_done.py` — `--ticket <path>` reads `source_ac` from
  the ticket frontmatter, looks up the AC, flips `work_status` to `done`
  (idempotent no-op if already done; refuses unless AC `status: active`; exit
  0/1/2). Tests: `tests/ac_store/test_mark_ac_done.py`.
- `scripts/commit_guardian/hooks/check_ac_done_on_merge.py` — the post-merge
  githook that *would* call `mark_ac_done` but never fires under `gh pr merge`
  (server-side merge + fast-forward pull; wrong `HEAD~1 HEAD` base for a squash).
  Left in place as a harmless belt-and-suspenders path (idempotency makes
  double-invocation safe) — see Out of Scope.

### Where the new step goes

Insert a new closure step **between Step 3 (test+triage gate) and Step 4 (PR
merge)**, running inside the feature worktree on the feature branch:

1. **Reset the test-merge first.** Step 2 ran `git merge origin/main --no-commit
   --no-ff` purely to test against the post-merge tree; it leaves a staged merge
   in the index. The closure step MUST `git merge --abort` (or `git reset --hard
   HEAD` to the branch tip) before committing, or the closure commit will drag a
   premature origin/main merge into the PR. Re-establish a clean feature-branch
   working tree, then make edits.
2. **Determine the tickets to close.** Use the same scope detection Step 6b uses
   (single-ticket vs epic; the set of ticket files on this branch with
   `status != done`). For each: set frontmatter `status: done`. For epics, also
   handle the Master_Plan / sub-ticket archival status per the existing
   archive-check rules — but **status flips only; no `git mv` on main** (folder
   reconciliation stays with ticket 04's domain / `status:`-as-truth model).
3. **Close the source ACs.** For each ticket being closed, invoke
   `mark_ac_done.py --ticket <path> --ac-root docs/acceptance-criteria/`.
4. **Commit on the feature branch** (one commit, e.g. `chore(tickets): close
   tickets and source ACs`), so the PR merge (Step 4) carries it to origin/main.

### Design notes

- **Non-fatal AC closure.** A failure to close an AC must never fail finalize or
  block the merge — log a WARNING and continue (mirror `check_ac_done_on_merge.py`).
  `mark_ac_done.py` returns exit 2 (not 1) for a non-`active` AC; treat any
  non-zero as a logged skip.
- **Idempotent / resumable.** Re-running finalize after a partial run must not
  error: tickets already `status: done` and ACs already `work_status: done` are
  no-ops. If the PR already merged (Step 4 resumability probe), the pre-merge
  commit is moot — detect and skip rather than attempting a main-side write.
- **Honest reporting.** Surface real counts (`tickets_closed`, `acs_closed`,
  `acs_skipped`) in the return payload and summary; never claim closure when the
  set was empty.
- **Commit delegation.** finalize-feature.js already commits via its agent/shell
  mechanism; route this closure commit the same way (respect the repo's commit
  conventions / hooks).
- Internal sub-step of an existing workflow — not a new user-facing surface, so
  no `user_facing_surface` / Smoke Fixture block is needed.

## Acceptance Criteria

- [ ] AC-1: Finalize sets ticket `status: done` and each ticket's `source_ac`
  `work_status: done` on the **feature branch**, in a commit created **before**
  the Step 4 PR merge, so closure reaches `origin/main` via the PR (no
  closure write on local `main`).
- [ ] AC-2: Before making closure edits, the step resets/aborts the Step 2
  `--no-commit --no-ff` test-merge so the closure commit contains only the
  ticket/AC changes — no premature `origin/main` merge content.
- [ ] AC-3: A ticket with no `source_ac` closes its `status` normally and the AC
  step is a silent no-op (no error, no failure).
- [ ] AC-4: AC closure is non-fatal: any non-zero `mark_ac_done.py` exit (AC not
  found, AC not `active`, read error) is logged as a WARNING; finalize proceeds
  to the merge and to a successful return.
- [ ] AC-5: The step is idempotent and resumable — re-running finalize does not
  error on already-closed tickets/ACs, and when the PR is already merged it skips
  rather than attempting a main-side write.
- [ ] AC-6: The return payload reports the real counts of tickets and ACs closed;
  the success message never claims closure when none occurred.
- [ ] AC-7: The step-map doc (`templates/workflows/finalize-feature.md`) is
  updated to show closure happening pre-merge (between the test gate and the PR
  merge), consistent with ticket 04 removing main-side moves/commits.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Sign-offs
- [x] test-writer — 2026-06-24 00:00
- [x] python-coder — 2026-06-24 12:00
- [x] test-runner — 2026-06-24 10:50
- [x] pr-reviewer — 2026-06-24 13:00
- [x] commit — 2026-06-24 14:00
- [x] pull-request — 2026-06-24 14:30

## Comments

### 2026-06-24 00:01 — ticket-supervisor (status: ok)
feedback-id: (submit-failed)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-24 12:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Implemented step 3.5 (pre-merge AC closure) in `templates/workflows-js/finalize-feature.js`.

### 2026-06-24 10:50 — test-runner (status: ok)
feedback-id: fb_2026-06-24_64dd2236
completion_manifest:
  primary_tests_green: true
  regression_tests_green: true
  all_acs_covered: true
All 11 tests in `tests/test_finalize_feature_closure.js` pass GREEN, covering AC-1 through AC-7. The 6 existing triage integration tests in `tests/test_finalize_feature_triage_integration.js` also pass GREEN — no regressions.

Changes made:
- Added `ticketsClosedPreMerge`, `acsClosed`, `acsSkipped` tracking variables alongside existing closure tracking.
- Updated `meta.phases` array to include the new step-3.5 entry.
- Inserted the step-3.5 block between the step-3 triage gate and the step-4 PR merge gate. The block:
  - (AC-5) Probes for an existing closure commit (`chore(tickets): close tickets and source ACs`) and skips if found.
  - (AC-5) Probes PR state and skips if PR is already merged.
  - (AC-2) Sub-step A: checks MERGE_HEAD; runs `git merge --abort` if merge is in progress, else `git reset --hard HEAD`.
  - (AC-1/AC-3/AC-4) Sub-step B-E agent call: finds open tickets on the branch, sets `status: done` in frontmatter, invokes `mark_ac_done.py` non-fatally (WARNING on non-zero exit), commits on the feature branch.
  - (AC-6) Accumulates counts into `ticketsClosedPreMerge`, `acsClosed`, `acsSkipped`.
- Updated final return payload to expose `tickets_closed_pre_merge`, `acs_closed`, `acs_skipped`.
- Updated final summary message to report honest counts (guards empty set with "No pre-merge ticket/AC closure.").
- (AC-7) Updated `templates/workflows/finalize-feature.md`: added step-3.5 row to step map between steps 3 and 4, updated frontmatter description.
- Added `tests/test_finalize_feature_closure.js` with 11 passing tests covering all 7 ACs (structural, behavioral, and unit-level).
- Existing triage integration tests (6 tests) still pass GREEN.

### 2026-06-24 13:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-24_4ef88097
completion_manifest:
  AC-1_closure_pre_merge: true
  AC-2_test_merge_reset: true
  AC-3_no_source_ac_noop: true
  AC-4_mark_ac_done_nonfatal: true
  AC-5_idempotent_resumable: true
  AC-6_honest_counts_in_payload: true
  AC-7_doc_updated: true
All 7 ACs verified against the diff. Step 3.5 is correctly inserted between `completedSteps.push(3)` and the step-4 block. Sub-step A resets the test-merge via MERGE_HEAD probe before any ticket edits. `source_ac` absence is handled as a silent no-op. Non-zero `mark_ac_done.py` exit produces a WARNING and does not fail finalize. Two idempotency probes (closure-commit-exists and PR-already-merged) guard re-entrancy. Return payload exposes `tickets_closed_pre_merge`, `acs_closed`, `acs_skipped`; the summary message is guarded by `ticketsClosedPreMerge > 0`. `finalize-feature.md` step-map table and frontmatter description are updated. No high-confidence blockers found.

### 2026-06-24 14:00 — commit (status: ok)
feedback-id: (submit-failed)
Committed feat(finalize): close tickets and source ACs pre-merge on feature branch.
Staged files: templates/workflows-js/finalize-feature.js, templates/workflows/finalize-feature.md, tests/test_finalize_feature_closure.js, tickets/00_inbox/epics/EPIC-FinalizeFeatureHardening/10_close_acs_on_finalize.md.

### 2026-06-24 14:30 — pull-request (status: ok)
feedback-id: fb_2026-06-24_386b9c7d
completion_manifest:
  branch_pushed: true
  pr_updated: true
Pushed commit c8bcc93 to branch EPIC-FinalizeFeatureHardening. Epic PR #158 already exists and has been updated with this ticket's changes. No new PR opened (shared-PR convention for this epic).

## Implementation Tasks
- [x] Add a closure step to `finalize-feature.js` after Step 3 (test+triage
  pass) and before Step 4 (PR merge), running in the feature worktree.
- [x] First action of the step: `git merge --abort` / reset to the feature-branch
  tip to discard the Step 2 test-merge before editing.
- [x] Flip frontmatter `status: done` for the in-scope ticket(s) (reuse Step 6b
  scope detection; status flips only, no `git mv`).
- [x] For each closed ticket, invoke `mark_ac_done.py --ticket <path> --ac-root
  docs/acceptance-criteria/`; wrap so non-zero exit is logged, not fatal.
- [x] Commit the closure on the feature branch (single commit) via the workflow's
  commit mechanism.
- [x] Accumulate `tickets_closed` / `acs_closed` / `acs_skipped`; thread into the
  return payload and human summary.
- [x] Make the step resumable (skip when PR already merged / already closed).
- [x] Update `templates/workflows/finalize-feature.md` (and the `meta.phases`
  step list) to reflect pre-merge closure.
- [x] Tests (extend `tests/test_finalize_feature_triage_integration.js` or add a
  sibling): (a) ticket+AC closed pre-merge on the branch; (b) test-merge is reset
  so the closure commit is clean; (c) ticket without `source_ac` is a no-op;
  (d) `mark_ac_done` failure does not fail finalize; (e) empty close set reports
  zero and makes no false claim.

## Out of Scope
- Removing/rewiring `check_ac_done_on_merge.py`. It stays as a harmless
  belt-and-suspenders path; `mark_ac_done.py` idempotency makes any
  double-invocation safe. Deduping the two paths is a separate cleanup.
- Folder reconciliation / `git mv` semantics on main — owned by ticket 04
  (`status:`-as-source-of-truth). This ticket only flips frontmatter `status:`.
- Adding a `shipped_by` (PR/commit) field to the AC — the larger "AC-as-record"
  refactor, not required to close the `work_status` loop.

## Risk & Safety
- Touches money? No.
- Touches data? Writes `status: done` to ticket files and `work_status: done` to
  AC YAML files — the intended effect, on the feature branch. Idempotent;
  targeted single-line replacement via `mark_ac_done.py`. Reversible by editing.
- Reversibility? High — additive workflow step + doc update; revert the commit.
  The pre-merge commit lives on the feature branch, so a pre-merge abort leaves
  no trace on main.
