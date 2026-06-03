---
title: "Remove _move_ticket() call from setup_ticket_worktree.py"
status: done
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/scripts/setup_ticket_worktree.py
  - tests/test_setup_ticket_worktree.py
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# 01: Remove _move_ticket() call from setup_ticket_worktree.py

## Actor / Goal

In order to stop branches from doing `git mv` of ticket files (the root
cause of worktree merge duplicates), we need to remove the `_move_ticket()`
invocation from the `setup-ticket` subcommand in `setup_ticket_worktree.py`,
so that the script only creates the worktree and bootstraps it — ticket
folder position is never mutated by the script.

## Context

`setup_ticket_worktree.py::setup_ticket()` (line ~403) calls
`_move_ticket(ticket_path, worktree_path)` which does `git mv
tickets/00_inbox/<name> tickets/01_todo/<name>` inside the newly-created
worktree. This is the exact operation that causes rename-tracking failures
during merges back to main: when the merge base predates the ticket file,
git sees `01_todo/<name>` as a new add rather than a rename, leaving a
stale copy in `00_inbox/`.

The `_move_ticket()` function itself should be **removed entirely** (not
just the call site) since there will be no remaining callers after this
ticket and ticket 02 land. Its docstring and the `# Must be under
tickets/00_inbox/ or tickets/01_todo/` validation block above it (lines
206–213) should be tightened to reflect that the script no longer performs
moves.

The path validation in `_validate_ticket_path()` currently accepts both
`00_inbox/` and `01_todo/` as valid locations. After this change the script
should still accept both (so in-flight tickets in `01_todo/` can have
worktrees created against them) but should never `git mv` the file.

### Dependency chain

Ticket 02 (`build-single-ticket/SKILL.md`) removes the separate Step 3
pre-move logic that relied on the same underlying `git mv` pattern. Both
tickets can land independently but should be reviewed together so that the
two call sites are removed in the same epic pass.

Ticket 03 (`finalize-feature.js`) adds the compensating folder reconciliation
on main. Until ticket 03 lands, ticket files will stay in `00_inbox/` even
when their frontmatter status is `done`. This is acceptable because the
lifecycle folders are informational, not operational: `ticket-supervisor`
routes on frontmatter status, not physical folder.

## Acceptance Criteria

```gherkin
Given setup_ticket_worktree.py setup-ticket is called with a ticket in 00_inbox/
When the script exits 0
Then the ticket file remains in 00_inbox/ (no git mv was performed)
 And the worktree is created and bootstrapped normally
 And git diff --cached --name-status inside the worktree shows NO rename (R) entry for the ticket file

Given setup_ticket_worktree.py setup-ticket is called with a ticket already in 01_todo/
When the script exits 0
Then the ticket file remains in 01_todo/ (idempotent, no move attempted)
 And the worktree is created and bootstrapped normally

Given the _move_ticket function is searched for in the module
When grep -n "_move_ticket" templates/scripts/setup_ticket_worktree.py is run
Then the function is absent (zero matches)
```

## Sign-offs

- [x] architect-review — 2026-06-03 10:00
- [x] test-writer — 2026-06-03 10:01
- [x] python-coder — 2026-06-03 10:02
- [x] test-runner — 2026-06-03 10:03
- [x] pr-reviewer — 2026-06-03 10:04
- [x] commit — 2026-06-03 10:05
- [x] pull-request — 2026-06-03 10:06

## Comments

### 2026-06-03 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-03_c2e3dbef
completion_manifest:
  design_approved: true
  no_adr_required: true
  test_plan_sound: true
Pure-subtraction change: removing `_move_ticket()` and its call site is architecturally correct — branches must never move ticket files to avoid merge-rename tracking failures. The path-validation logic retaining both `00_inbox/` and `01_todo/` is appropriate for idempotency. The JSON output field rename from `ticket_path_new` to `ticket_path_final` is a clean, non-breaking change within the epic branch. No ADR required. Test plan in Implementation Tasks covers all acceptance criteria. Approved.

### 2026-06-03 10:01 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-03 10:02 — python-coder (status: ok)
feedback-id: fb_2026-06-03_bca65fde
completion_manifest:
  move_ticket_function_removed: true
  call_site_removed: true
  output_field_renamed: true
  validate_ticket_docstring_updated: true
  decision_history_added: true
  new_tests_written: true
  all_tests_green: true
Removed `_move_ticket()` function and call site entirely; renamed JSON output field `ticket_path_new` → `ticket_path_final`; updated `_validate_ticket()` docstring to clarify both lifecycle folders remain valid without implying a move; added DECISION HISTORY entry. Added 3 new tests (`test_setup_ticket_does_not_move_ticket_file`, `test_setup_ticket_accepts_01_todo_ticket`, `test_move_ticket_function_absent`). All 7 tests green; ruff E722/BLE001/TRY clean.

### 2026-06-03 10:03 — test-runner (status: ok)
feedback-id: fb_2026-06-03_faee8b0b
completion_manifest:
  all_tests_pass: true
  no_ruff_violations: true
  acceptance_criteria_covered: true
7/7 tests pass (4 pre-existing bootstrap tests + 3 new no-move tests). Ruff E722/BLE001/TRY clean on both `setup_ticket_worktree.py` and `test_setup_ticket_worktree.py`. All three acceptance criteria from the Gherkin block are covered by the test suite.

### 2026-06-03 10:04 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_dc243a11
completion_manifest:
  implementation_correct: true
  no_dead_code: true
  tests_adequate: true
  docstrings_accurate: true
  decision_history_present: true
Change is correct and complete. Identified and fixed stale references to "ticket move" in the module-level docstring (`GOAL`, `ARCHITECTURE`), the argparse top-level `description`, and the `cmd_setup_ticket` docstring — all still said "ticket move" after the removal. Updated all three to accurately reflect the no-move behavior. All 7 tests pass after the docstring fixes. Approved.

### 2026-06-03 10:05 — commit (status: ok)
feedback-id: fb_2026-06-03_2ee7493e
completion_manifest:
  commit_succeeded: true
  correct_files_staged: true
  lock_acquired_and_released: true
4 files committed cleanly (SHA 5ce21d1): `setup_ticket_worktree.py`, `test_setup_ticket_worktree.py`, `01_remove_move_ticket_from_worktree_setup.md`, `feedback.jsonl`. Commit-phase lock acquired before staging and released after success. Pre-commit config absent in worktree (epic branch), hooks will apply on main after PR merge.

### 2026-06-03 10:06 — pull-request (status: ok)
feedback-id: fb_2026-06-03_2c9fdcee
completion_manifest:
  pr_opened: true
  branch_pushed: true
PR #36 opened at https://github.com/urlmonitor/leafcutter-ai/pull/36 for epic branch EPIC-MoveOnMainOnly → main. Branch pushed (SHA 1c72715). One PR per epic, covering all tickets in EPIC-MoveOnMainOnly.

## Implementation Tasks

### python-coder

- [x] In `setup_ticket_worktree.py`, remove the `_move_ticket()` function
  definition entirely (lines ~228–261 in the current template).
- [x] Remove the call site `ticket_path_new = _move_ticket(ticket_path,
  worktree_path)` from the `setup_ticket()` function (line ~403). Replace
  the subsequent uses of `ticket_path_new` with `ticket_path` (the original
  path, unchanged).
- [x] Update the return value from `setup_ticket()` — the JSON output field
  `ticket_path_new` should be renamed to `ticket_path_final` (or simply
  `ticket_path`) to make clear that the file location was NOT changed.
  Callers (build-single-ticket SKILL.md) parse this field; coordinate with
  ticket 02's changes so both are updated in the same epic branch.
- [x] Tighten the `_validate_ticket_path()` function: remove the comment
  `# Must be under tickets/00_inbox/ or tickets/01_todo/` and update the
  docstring to clarify that the function validates ticket existence but does
  not constrain which lifecycle folder is acceptable (both remain valid for
  worktree creation).
- [x] Add a dated DECISION HISTORY entry to the module-level docstring:
  `"YYYY-MM-DD [EPIC-MoveOnMainOnly/01]: Removed _move_ticket() — branches
  no longer move ticket files; finalize-feature.js reconciles folder
  position on main after merge."`

### test-writer

- [x] In `tests/test_setup_ticket_worktree.py`, add
  `test_setup_ticket_does_not_move_ticket_file`: mock the worktree
  creation and bootstrap helpers; invoke the `setup-ticket` subcommand
  with a ticket in `00_inbox/`; assert that `git mv` was never called and
  that the returned JSON contains the original `00_inbox/` path.
- [x] Add `test_setup_ticket_accepts_01_todo_ticket`: invoke with a ticket
  already in `01_todo/`; assert the script exits 0 and no git mv is issued.
- [x] Remove or update any existing tests that mock or assert `_move_ticket`
  being called — those assertions are now dead.

## Risk & Safety

- Touches money? No.
- Touches data? No — ticket files are not moved; their content is unchanged.
- Reversibility? The removal is a pure subtraction. Reverting is a
  one-commit revert. In-flight worktrees bootstrapped before this change
  already have the ticket in `01_todo/`; they are unaffected.
- The compensating folder reconciliation (ticket 03) must land before
  `/finalize-feature` is expected to close tickets reliably. Until then,
  ticket files stay in their creation folder regardless of frontmatter
  status — which is the safe failure mode (files are not lost, just in
  the "wrong" folder).
