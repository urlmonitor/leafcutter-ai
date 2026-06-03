---
title: "New pre-commit hook check_ticket_no_branch_move.py"
status: done
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_remove_move_ticket_from_worktree_setup.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/hooks/check_ticket_no_branch_move.py
  - templates/commit-guardian/commit_guardian.json
  - templates/commit-guardian/hooks_manifest.json
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
  user-surface-smoker: signed_off
user_facing_surface: pre_commit_hook
actuation_contract: "Inspects the git staged index for R (rename) entries whose source or destination paths match the tickets/ directory tree; if running on a non-main/master branch and a rename is detected, exits non-zero with a descriptive error message directing the author to edit frontmatter status instead."
---

# 04: New pre-commit hook check_ticket_no_branch_move.py

## Actor / Goal

In order to enforce the move-on-main-only pattern at the point of commit
(belt-and-suspenders), we need a new pre-commit hook
`check_ticket_no_branch_move.py` that blocks `git mv` of ticket files on
non-main/master branches, so that authors cannot accidentally bypass the
pattern even when not using `setup_ticket_worktree.py` directly.

## Context

The move-on-main-only pattern requires that branches **never** rename ticket
files between lifecycle folders. Tickets 01 and 02 remove the automated
`git mv` calls from the tooling, but a developer (or an agent writing custom
bash) could still manually run `git mv tickets/00_inbox/TICKET-X.md
tickets/01_todo/TICKET-X.md` and commit it. This hook closes that gap.

### Existing hook complement

`check_ticket_rename_tracking.py` (PostToolUse hook) fires after a `git mv`
Bash call and verifies that the rename is properly tracked in the staged
index. That hook is a *correctness* guard for renames that have already been
staged. The new hook is a *policy* guard that blocks the commit entirely if
any ticket rename appears in the staged index on a non-main branch.

The two hooks are complementary:
- `check_ticket_rename_tracking.py` — fires on PostToolUse (Bash with git mv)
- `check_ticket_no_branch_move.py` — fires at pre-commit time on the full
  staged index

### Detection logic

Pre-commit hooks receive no stdin payload — they inspect the working tree
directly. The hook should:

1. Determine current branch: `git rev-parse --abbrev-ref HEAD`.
2. If branch is `main` or `master`: exit 0 immediately (moves are allowed on main).
3. Run `git diff --cached --name-status -M` and parse for `R` (rename) entries.
4. For each `R` entry, check if source OR destination path starts with
   `tickets/`.
5. If any ticket rename is found: exit non-zero with:
   ```
   [no-branch-ticket-move] ERROR: ticket file renamed on a non-main branch.
   Source: <old_path>
   Dest:   <new_path>
   Branch: <current_branch>

   Branches must NOT move ticket files between lifecycle folders (move-on-main-only
   pattern, EPIC-MoveOnMainOnly). Instead:
     - Edit the ticket's frontmatter `status:` field to reflect the new state.
     - The folder move happens automatically on main after merge via
       finalize-feature.js Step 5.

   If you intentionally need to commit this rename (e.g. fixing a duplicate),
   switch to main or use git commit --no-verify with explicit justification.
   ```
6. If no ticket renames found: exit 0.

### Hook registration

The hook must be registered in `commit_guardian.json` (or `hooks_manifest.json`
if the project uses a separate manifest) as a `pre_commit` hook targeting all
commits. See `check_ticket_rename_tracking.py` registration pattern for the
exact JSON schema.

### Deployment path

The hook lives in `templates/hooks/` and is deployed to adopter projects via
the leafcutter build pipeline. Adopters with an existing `commit_guardian.json`
get the hook on their next `build.py --force` run.

## Acceptance Criteria

```gherkin
Given a developer runs git commit on a non-main branch
 And the staged index contains a rename of a file under tickets/
When the pre-commit hook fires
Then the commit is blocked with exit code 1
 And the error message includes "no-branch-ticket-move"
 And the error message names the source and destination paths
 And the error message explains the move-on-main-only pattern

Given a developer runs git commit on the main branch
 And the staged index contains a rename of a file under tickets/
When the pre-commit hook fires
Then the commit is allowed (exit 0)

Given a developer runs git commit on a non-main branch
 And the staged index contains ONLY non-rename changes to ticket files (e.g. frontmatter edits)
When the pre-commit hook fires
Then the commit is allowed (exit 0)

Given a developer runs git commit on a non-main branch
 And the staged index contains renames of non-ticket files (e.g. docs/ renames)
When the pre-commit hook fires
Then the commit is allowed (exit 0)
```

## Smoke Fixture

```yaml
surface: check_ticket_no_branch_move
fixture_input: |
  branch: feature/test-branch
  staged_renames:
    - src: tickets/00_inbox/TICKET-20260101-Test.md
      dst: tickets/01_todo/TICKET-20260101-Test.md
assertion: "no-branch-ticket-move.*ERROR"
placeholder_signature: "pass|TODO|not implemented"
```

## Sign-offs

- [x] architect-review — 2026-06-03 10:00
- [x] test-writer — 2026-06-03 10:05
- [x] python-coder — 2026-06-03 10:15
- [x] test-runner — 2026-06-03 10:20
- [x] pr-reviewer — 2026-06-03 10:25
- [x] commit — 2026-06-03 10:35
- [x] pull-request — 2026-06-03 10:40
- [x] user-surface-smoker — 2026-06-03 10:30

## Comments

### 2026-06-03 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-03_1dc23306
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Impact: SMALL. Affected files: templates/hooks/check_ticket_no_branch_move.py (new), templates/commit-guardian/commit_guardian.json (update). Single component: build_pipeline. No always-large triggers (no Alembic migration, no hypertable change, no public API change, no ADR contract change). No ADR required. No diagram needed. Hook is self-contained (stdlib only), complements check_ticket_rename_tracking.py as a policy gate at commit time.

## Escalation

Branch: none
Reason: 2 files in 1 component (build_pipeline); no always-large trigger fired.

### 2026-06-03 10:05 — test-writer (status: ok)
feedback-id: fb_2026-06-03_e7021f43
completion_manifest:
  test_stubs_created: true
  red_baseline_confirmed: true
  test_file_path_matches_plan: true
Created tests/test_check_ticket_no_branch_move.py with 5 test cases covering all acceptance criteria: blocks on feature branch with ticket rename (exit 1 + "no-branch-ticket-move"), allows on main branch, allows non-ticket renames, allows empty rename list, blocks rename to 99_done/ on non-main branch. All 5 tests are RED (FileNotFoundError — hook not yet implemented), confirming the TDD baseline.

### 2026-06-03 10:15 — python-coder (status: ok)
feedback-id: fb_2026-06-03_b9ff4bd2
completion_manifest:
  hook_file_created: true
  hook_registered_in_commit_guardian: true
  ruff_clean: true
  all_tests_green: true
Created templates/hooks/check_ticket_no_branch_move.py with _current_branch(), _get_staged_renames(), _is_ticket_path(), and main() per spec. Fixed two TRY300 Ruff violations (subprocess.run calls restructured with try/except/else pattern). Registered hook in templates/commit-guardian/commit_guardian.json under hooks_manifest.hooks as "check-ticket-no-branch-move". All 5 tests now pass (were RED before implementation).

### 2026-06-03 10:20 — test-runner (status: ok)
feedback-id: fb_2026-06-03_3b9685f3
completion_manifest:
  ticket_tests_green: true
  no_regressions: true
5/5 ticket tests pass. Full suite: 275 passed, 4 pre-existing failures (test_emit_entry_cwd x2, test_install_hooks, test_skill_registry — all unrelated to this ticket, none touch check_ticket_no_branch_move). No regressions introduced.

### 2026-06-03 10:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_63ef6585
completion_manifest:
  acceptance_criteria_covered: true
  error_message_format_correct: true
  fail_open_behaviour_verified: true
  hook_registration_correct: true
  ruff_clean: true
  no_external_dependencies: true
All 4 acceptance criteria scenarios are correctly handled by the implementation. Error message includes "no-branch-ticket-move", source, dest, branch, policy explanation, and --no-verify escape hatch exactly as specified. Fail-open on subprocess errors (returns "main" / empty list). Hook registration in commit_guardian.json uses correct entry path convention and pass_filenames: false. No blocking issues.

### 2026-06-03 10:30 — user-surface-smoker (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  placeholder_check_passed: true
  smoke_fixture_assertion_matched: true
  exit_code_correct: true
No placeholder signature found. Smoke fixture exercised: branch=feature/test-branch + ticket rename staged → exit 1 with output matching "no-branch-ticket-move.*ERROR". Output preview: "[no-branch-ticket-move] ERROR: ticket file renamed on a non-main branch. Source: tickets/00_inbox/TICKET-20260101-Test.md...". Surface wired correctly end-to-end.

### 2026-06-03 10:35 — commit (status: ok)
feedback-id: fb_2026-06-03_018ba4bd
completion_manifest:
  files_staged_explicitly: true
  commit_succeeded: true
  no_cross_worktree_pollution: true
Staged 4 files explicitly by path (no git add -A): templates/hooks/check_ticket_no_branch_move.py, templates/commit-guardian/commit_guardian.json, tests/test_check_ticket_no_branch_move.py, tickets/.../04_hook_block_branch_ticket_move.md. Commit a780eb7 landed on EPIC-MoveOnMainOnly branch. 4 files changed, 424 insertions, 20 deletions. Lock acquired before commit, released after.

### 2026-06-03 10:40 — pull-request (status: ok)
feedback-id: fb_2026-06-03_9335753c
completion_manifest:
  commit_pushed: true
  pr_available: true
PR #36 (EPIC-MoveOnMainOnly: stop branches from moving ticket files) already exists and is OPEN. Pushed commit a780eb7 to origin/EPIC-MoveOnMainOnly — ticket 04 implementation is now included in the existing epic PR. No new PR needed (one PR per epic convention).

## Implementation Tasks

### python-coder

- [x] Create `templates/hooks/check_ticket_no_branch_move.py` with:
  - Module docstring following the `MODULE / GOAL / BUSINESS CONTEXT /
    ARCHITECTURE / DECISION HISTORY` format from sibling hooks.
  - `_current_branch() -> str`: runs `git rev-parse --abbrev-ref HEAD`;
    returns `"main"` on error (fail-open).
  - `_get_staged_renames() -> list[tuple[str, str]]`: runs
    `git diff --cached --name-status -M`; parses `R\t<src>\t<dst>` lines;
    returns list of (src, dst) tuples.
  - `_is_ticket_path(path: str) -> bool`: returns `path.startswith("tickets/")`.
  - `main()`: orchestrates the detection and exit logic described above.
  - No external dependencies — pure stdlib (subprocess, sys).
  - Pre-commit hook contract: reads nothing from stdin; exit 0 = allow,
    exit non-zero = block.
- [x] Register the hook in `templates/commit-guardian/commit_guardian.json`
  (or `hooks_manifest.json`) under the `pre_commit` hooks list. Use the same
  schema entry format as `check_ticket_rename_tracking.py` (if that hook is
  registered there) or follow the existing `pre_commit` entry pattern.

### test-writer

- [x] Create `tests/test_check_ticket_no_branch_move.py`.
- [x] `test_blocks_ticket_rename_on_feature_branch`: mock `_current_branch` to
  return `"feature/my-branch"`; mock `_get_staged_renames` to return
  `[("tickets/00_inbox/T.md", "tickets/01_todo/T.md")]`; assert `main()`
  exits with code 1 and prints "no-branch-ticket-move".
- [x] `test_allows_ticket_rename_on_main`: mock `_current_branch` to return
  `"main"`; same renames; assert `main()` exits 0.
- [x] `test_allows_non_ticket_rename_on_feature_branch`: mock renames for
  `docs/README.md → docs/GUIDE.md`; assert `main()` exits 0.
- [x] `test_allows_no_renames`: mock empty rename list; assert `main()` exits 0.
- [x] `test_blocks_on_master_branch_rename`: mock branch `"not-main"` and
  renames with destination in `tickets/99_done/`; assert exit 1.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The hook can be disabled per-commit with `--no-verify`
  (intentional escape hatch with explicit justification required).
- False positive risk: low. The only files under `tickets/` are ticket
  markdown files; any rename of them on a non-main branch is policy-violating
  by construction.
- False negative risk: the hook only fires at commit time. A developer could
  stage a rename, switch to main, and commit — but that is the allowed
  path. The hook correctly passes on main.
