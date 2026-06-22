---
title: "Retrospective: EPIC-GoalToEpicLeafFilter"
description: "Epic retrospective for EPIC-GoalToEpicLeafFilter — leaf filter correctness fixes for scan_ac_store.py (done/superseded exclusion and out-of-scope cycle resilience)."
date: 2026-06-22
epic_branch: EPIC-GoalToEpicLeafFilter
pr: "https://github.com/urlmonitor/leafcutter-ai/pull/136"
---

# Retrospective: EPIC-GoalToEpicLeafFilter

Date: 2026-06-22
Epic duration: 2026-06-22 (branch opened and merged same day)
Commits: 1 squash-merge (PR #136, 6 files changed, 1149 insertions, 15 deletions)

---

## Summary

EPIC-GoalToEpicLeafFilter fixed two correctness gaps in `scripts/ac_store/scan_ac_store.py`
that surfaced while processing the EPIC-CodeQualityHooks retrospective findings.

Ticket 01 (ACD-1200a-10) added `exclude_done` and `exclude_superseded` flags to
`traverse_ac_tree()` so that goal mode no longer emits tickets for work already
marked `done` or for superseded ACs. The fix recursively descends into a superseded
AC's `covered_by` children so replacement leaves are still collected — the pruning is
smart, not blunt. New test file `unit_tests/ac_store/test_leaf_filter.py` covers the
core exclusion, the recurse-into-superseded path, and the flag-disabled baseline.

Ticket 02 (ACD-1200c-3) made store-wide scans resilient to out-of-scope dependency
cycles. A pre-existing cycle (`BO-1100a-3 ↔ BO-1100d-1`) had been hard-aborting
every `/build-ac` ranking run, blocking unrelated trees. The fix degrades the crash
to a warning and continues ranking the acyclic remainder; a genuine intra-scope cycle
in a goal build still hard-fails (the ACD-1200c-1-i guard is preserved, not weakened).
New test file `unit_tests/ac_store/test_scan_ac_store_cycle.py` covers both behaviors.

Both ACs had been authored and approved on `main` (PR #133) before the epic branch was
cut. The implementation was a single-day drive that delivered both fixes, both test
suites, and the ticket scaffolding in one squash-merge commit.

---

## Metrics

| Ticket | Description | Status |
|--------|-------------|--------|
| 01 (ACD-1200a-10) | `traverse_ac_tree()` excludes done/superseded leaves; recurse into superseded `covered_by`; `exclude_done`/`exclude_superseded` flags | done |
| 02 (ACD-1200c-3) | Store-wide scan degrades out-of-scope cycles to warning; scoped goal build still hard-fails | done |

Both tickets completed. 2 of 2 done.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 2 |
| Completed tickets | 2 |
| Git commits (PR branch) | 1 squash-merge (PR #136) |
| Files changed | 6 |
| Lines added | +1149 (including 580 lines of new unit tests) |
| Lines changed in production code | +133 / -15 in `scan_ac_store.py` |
| Blocker comments | 0 |
| Handoff comments | 0 |
| Post-merge CI failures (new) | 0 (3 failures confirmed pre-existing baseline) |
| Fix commit needed before merge | 1 (ruff F401: 2 unused imports) |

No structured feedback entries are scoped to this epic's ticket paths in
`feedback.jsonl` — the tickets were authored and implemented on the same day
without invoking the feedback pipeline's per-phase emit step.

---

## What Went Well

- **AC-first ordering eliminated scope ambiguity.** Both ACs (ACD-1200a-10 and
  ACD-1200c-3) were authored, reviewed, and merged to `main` (PR #133) before the
  implementation branch was cut. When the drive started, the acceptance criteria were
  contractual — no mid-implementation scope negotiation occurred.

- **Flag-gated implementation was a clean design.** The `exclude_done` and
  `exclude_superseded` parameters defaulted to `True` (new behavior) while remaining
  testable with `False` (old behavior). This let the test suite prove both the new
  path and the legacy baseline in the same test file without mocking.

- **Cycle resilience preserved the intra-scope hard-fail.** The fix correctly threaded
  the needle: out-of-scope cycles degrade to a warning (correct for store-wide ranking),
  but a cycle within the goal build's own leaves still hard-fails. The regression guard
  test in `test_scan_ac_store_cycle.py` confirmed this distinction was not accidentally
  weakened.

- **Single-file scope.** Both fixes landed in `scripts/ac_store/scan_ac_store.py`.
  No cross-cutting agent template or pipeline changes were needed. The blast radius was
  narrow and well-understood before the drive began.

- **Post-merge test failures were all pre-existing.** Three failures discovered after
  merge (`test_goal_to_epic_worktree_skip`, `test_install_hooks`, `test_skill_registry`)
  were confirmed as pre-existing baseline failures unrelated to this epic's changes.
  No follow-up fix commit was required for them.

---

## Friction Points

- **Ruff F401 gate blocked the first CI run.** Two unused imports were left in the
  test files after implementation: `import pytest` in `test_leaf_filter.py` and
  `import io` in `test_scan_ac_store_cycle.py`. The ruff lint gate (added in PR #98)
  caught both and blocked the merge. A fix commit was required before CI went green.
  This is a recurring pattern — the worktree lacks a live pre-commit config during
  development (see the Worktree Pre-Commit Gap memory entry), so ruff does not fire
  locally. The fix is mechanical once identified but adds a round-trip to CI.

- **EMU account drift blocked the `gh pr merge` path.** `gh pr merge` uses the
  GraphQL `mergePullRequest` mutation, which is blocked for Enterprise Managed User
  (EMU) accounts. Even after switching to the `urlmonitor` account, the `gh` CLI
  reverts to `henzeh_roche` (EMU) between operations without warning. The workaround
  required using the REST endpoint directly:
  ```
  gh api -X PUT repos/urlmonitor/leafcutter-ai/pulls/136/merge
  ```
  The account must be verified (`gh auth status`) immediately before every write
  operation — not just at session start. A drift back to EMU between the `gh auth
  switch` and the actual command is possible and has been observed.

- **Two AC YAML back-ref edits were not committed.** `ACD-1200a-10.yaml` and
  `ACD-1200c-3.yaml` had stale loose-inbox `implemented_by` paths written by
  `generate_ticket_from_ac.py`. These were not committed as part of the epic because
  they contain paths to the temporary worktree location, not the merged `99_done`
  paths. They are not part of the delivered work but represent a known trailing edge
  in the `goal_to_epic.py` dual-write pattern (tracked in EPIC-GoalToEpicBugfixes /
  ACD-1200a-9).

---

## Knowledge Gaps Found

### KG-1: Unused imports in test files escape local linting (worktree pre-commit gap)

Test files produced by python-coder (or hand-written during a drive) regularly carry
unused imports that were scaffolded as part of a test stub and never removed. Because
the worktree lacks `.pre-commit-config.yaml` (the `.leafcutter` symlink is not created
in worktrees), ruff's F401 check does not fire locally. The first signal is the CI
ruff gate, requiring a fix commit.

The fix is known: run `ruff check --select F401` manually before pushing. The gap is
that no agent prompt or checklist reminds the driver to do this.

### KG-2: EMU account drift between `gh auth switch` and write operations

The `gh` CLI silently reverts to the EMU account (`henzeh_roche`) between operations
within the same session. A `gh auth switch --user urlmonitor` at the start of a
session does not reliably persist across subsequent commands. The `gh pr merge` path
is additionally blocked (GraphQL mutation forbidden for EMU), requiring the REST
fallback (`gh api -X PUT ...`). Neither the pre-drive checklist nor any agent template
currently captures the "verify immediately before each write" discipline.

---

## Subagent Quality Trends

No supervisor feedback entries found for this epic (no adjudication events occurred
during this drive — both tickets passed without blockers or retries).

---

## Proposed Improvements

### KI-1: Add F401 lint check reminder to the pre-drive (or pre-push) checklist

**Proposed addition to the Pre-Drive Checklist in `CLAUDE.md`:**

```diff
+ ### Ruff unused-import check before first push (test files)
+
+ Test files produced during a drive often retain scaffolded imports that are
+ never exercised. The worktree lacks a live pre-commit config, so ruff F401
+ does not fire locally. Run this before the first `git push`:
+
+ ```bash
+ ruff check --select F401 <worktree-root>/unit_tests/ <worktree-root>/tests/
+ ```
+
+ Fix any F401 findings before pushing to avoid a CI fix-commit round-trip.
+ Common offenders: `import pytest` (when only fixtures are used, not the
+ module directly), `import io` (when StringIO is used but io is not).
```

Routing: `CLAUDE.md-toc` — the existing `## Pre-Drive Checklist` section in
`CLAUDE.md` already links to the full checklist content. This item is a new
subsection within that checklist (content lives inline in the Pre-Drive Checklist
section of `CLAUDE.md` since the checklist is itself inline in CLAUDE.md).

**User approval required before applying.**

---

### KI-2: Strengthen the EMU pre-write auth check discipline

**Proposed addition to the `### EMU account: open epic PR before drive` section
in `CLAUDE.md`:**

```diff
+ **Account drift: verify immediately before every write operation, not just at
+ session start.**
+
+ `gh auth switch --user urlmonitor` does NOT reliably persist across subsequent
+ `gh` commands within the same session — the CLI has been observed silently
+ reverting to `henzeh_roche` (EMU) between commands. The sequence is:
+
+ ```bash
+ # Before EVERY write operation (pr create, pr merge, api call):
+ gh auth status   # confirm active account is urlmonitor
+ gh auth switch --user urlmonitor   # re-switch if needed
+ ```
+
+ **`gh pr merge` is always GraphQL-blocked for EMU.** Do not attempt it.
+ Use the REST fallback regardless of which account is active:
+
+ ```bash
+ gh api -X PUT repos/urlmonitor/leafcutter-ai/pulls/<N>/merge \
+   -f merge_method=squash \
+   -f commit_title="<title>"
+ ```
```

Routing: `CLAUDE.md-inline` (Step 4) — extends the existing EMU subsection already
present in the `## Pre-Drive Checklist` section of `CLAUDE.md`. The content is a
short behavioral correction (verify-before-each-write) plus the REST fallback reminder.
The existing section already documents the EMU block and the REST endpoint; this
addition adds the *drift-back* pattern that was not previously captured.

**User approval required before applying.**

---

*Proposed improvements above require explicit user approval before being applied.
No files beyond this retrospective have been modified.*
