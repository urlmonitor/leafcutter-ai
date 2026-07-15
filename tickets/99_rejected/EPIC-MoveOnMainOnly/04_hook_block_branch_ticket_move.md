---
title: "New pre-commit hook check_ticket_no_branch_move.py"
status: todo
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
  user-surface-smoker: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] user-surface-smoker

## Comments

## Implementation Tasks

### python-coder

- [ ] Create `templates/hooks/check_ticket_no_branch_move.py` with:
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
- [ ] Register the hook in `templates/commit-guardian/commit_guardian.json`
  (or `hooks_manifest.json`) under the `pre_commit` hooks list. Use the same
  schema entry format as `check_ticket_rename_tracking.py` (if that hook is
  registered there) or follow the existing `pre_commit` entry pattern.

### test-writer

- [ ] Create `tests/test_check_ticket_no_branch_move.py`.
- [ ] `test_blocks_ticket_rename_on_feature_branch`: mock `_current_branch` to
  return `"feature/my-branch"`; mock `_get_staged_renames` to return
  `[("tickets/00_inbox/T.md", "tickets/01_todo/T.md")]`; assert `main()`
  exits with code 1 and prints "no-branch-ticket-move".
- [ ] `test_allows_ticket_rename_on_main`: mock `_current_branch` to return
  `"main"`; same renames; assert `main()` exits 0.
- [ ] `test_allows_non_ticket_rename_on_feature_branch`: mock renames for
  `docs/README.md → docs/GUIDE.md`; assert `main()` exits 0.
- [ ] `test_allows_no_renames`: mock empty rename list; assert `main()` exits 0.
- [ ] `test_blocks_on_master_branch_rename`: mock branch `"not-main"` and
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
