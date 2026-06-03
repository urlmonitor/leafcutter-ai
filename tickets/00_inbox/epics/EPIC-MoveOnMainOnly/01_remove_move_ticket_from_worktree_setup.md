---
title: "Remove _move_ticket() call from setup_ticket_worktree.py"
status: todo
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
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] In `setup_ticket_worktree.py`, remove the `_move_ticket()` function
  definition entirely (lines ~228–261 in the current template).
- [ ] Remove the call site `ticket_path_new = _move_ticket(ticket_path,
  worktree_path)` from the `setup_ticket()` function (line ~403). Replace
  the subsequent uses of `ticket_path_new` with `ticket_path` (the original
  path, unchanged).
- [ ] Update the return value from `setup_ticket()` — the JSON output field
  `ticket_path_new` should be renamed to `ticket_path_final` (or simply
  `ticket_path`) to make clear that the file location was NOT changed.
  Callers (build-single-ticket SKILL.md) parse this field; coordinate with
  ticket 02's changes so both are updated in the same epic branch.
- [ ] Tighten the `_validate_ticket_path()` function: remove the comment
  `# Must be under tickets/00_inbox/ or tickets/01_todo/` and update the
  docstring to clarify that the function validates ticket existence but does
  not constrain which lifecycle folder is acceptable (both remain valid for
  worktree creation).
- [ ] Add a dated DECISION HISTORY entry to the module-level docstring:
  `"YYYY-MM-DD [EPIC-MoveOnMainOnly/01]: Removed _move_ticket() — branches
  no longer move ticket files; finalize-feature.js reconciles folder
  position on main after merge."`

### test-writer

- [ ] In `tests/test_setup_ticket_worktree.py`, add
  `test_setup_ticket_does_not_move_ticket_file`: mock the worktree
  creation and bootstrap helpers; invoke the `setup-ticket` subcommand
  with a ticket in `00_inbox/`; assert that `git mv` was never called and
  that the returned JSON contains the original `00_inbox/` path.
- [ ] Add `test_setup_ticket_accepts_01_todo_ticket`: invoke with a ticket
  already in `01_todo/`; assert the script exits 0 and no git mv is issued.
- [ ] Remove or update any existing tests that mock or assert `_move_ticket`
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
