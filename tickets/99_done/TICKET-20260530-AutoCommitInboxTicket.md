---
title: "Add PostToolUse hook to auto-commit and push standalone inbox tickets to main"
status: done
components:
  - build_pipeline
created: 2026-05-30
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/hooks/auto_commit_inbox_ticket.py
  - .claude/hooks/auto_commit_inbox_ticket.py
  - templates/settings.json
  - .claude/settings.json
  - unit_tests/commit_guardian/test_auto_commit_inbox_ticket.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  sql-query: not_needed
  frontend-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  pr-reviewer: signed_off
  user-surface-smoker: signed_off
  commit: signed_off
  pull-request: signed_off
  status-checker: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
user_facing_surface: pre_commit_hook
actuation_contract: "When create-ticket writes a .md file directly into tickets/00_inbox/ (not inside any subdirectory), the hook runs git add <file>, git commit -m 'chore(tickets): add <basename>', and git push origin main, printing a single confirmation line on success and a warning on any failure — silently no-op when the file is already committed, the current branch is not main, or the working tree is a git worktree on a non-main branch."
---

# Add PostToolUse hook to auto-commit and push standalone inbox tickets to main

## Actor / Goal

In order to eliminate the manual step of committing and pushing newly created
inbox tickets, we need a `PostToolUse` Claude Code hook that automatically
stages, commits, and pushes any standalone `.md` file written to
`tickets/00_inbox/` so that the ticket appears on `origin/main` immediately
after `create-ticket` writes it.

## Context

When `create-ticket` finishes, it writes a ticket file to
`tickets/00_inbox/TICKET-YYYYMMDD-Name.md`. The create-ticket orchestrator
already includes a Step 4 commit (depth-1 only), but that commit happens
inside the agent turn and requires the agent to remember to do it. In
practice, users have had to manually ask Claude to commit and push.

Inbox tickets are just work-item definitions — they contain no implementation
code, no secrets, and no partial state. Committing them to `main` immediately
is always safe. The only constraints are:

1. Do not commit if the file is already in a clean committed state (idempotency).
2. Do not push if the current branch is not `main` (avoids polluting a feature
   branch with ticket commits).
3. Do not push if we are inside a git worktree whose branch is not `main`
   (worktrees are always feature branches; their ticket work is bundled by
   `create-epic` in its Phase 5 commit).
4. Do not trigger for paths inside `tickets/00_inbox/epics/` or any deeper
   subdirectory — those are managed by the epic workflow which does its own
   bundled commit.

The hook follows the same structural pattern as other `PostToolUse` hooks
(`check_ticket_rename_tracking.py`, `ticket_frontmatter_guard.py`): a Python
script registered in `templates/settings.json` under the `PostToolUse /
Edit|Write` matcher, receiving the tool payload as JSON on stdin, and exiting
0 unconditionally (PostToolUse hooks cannot block).

Both `templates/settings.json` (the package source) and `.claude/settings.json`
(the deployed development copy) must be updated so the hook fires in the dev
environment immediately without waiting for a `build.py` rebuild.

## Acceptance Criteria

```gherkin
Given create-ticket writes tickets/00_inbox/TICKET-20260601-Foo.md on branch main
When the PostToolUse hook fires
Then the hook runs git add tickets/00_inbox/TICKET-20260601-Foo.md
  AND git commit -m "chore(tickets): add TICKET-20260601-Foo"
  AND git push origin main
  AND prints a single confirmation line to stdout

Given the file tickets/00_inbox/TICKET-20260601-Foo.md is already committed and clean
When the PostToolUse hook fires
Then the hook exits 0 without running git commit or git push

Given the current git branch is feature/my-epic (not main)
When the PostToolUse hook fires for an inbox ticket
Then the hook exits 0 without running git commit or git push
  AND prints a note that push is skipped because branch is not main

Given the working tree is a git worktree (not the main worktree)
When the PostToolUse hook fires for an inbox ticket
Then the hook exits 0 without running git commit or git push

Given the written file path is tickets/00_inbox/epics/EPIC-Foo/01_sub.md
When the PostToolUse hook fires
Then the hook exits 0 without any git operations (epic subfolder excluded)

Given the written file path is tickets/00_inbox/some-subdir/TICKET-X.md
When the PostToolUse hook fires
Then the hook exits 0 without any git operations (non-direct-child path excluded)

Given git push fails (e.g. network error or diverged remote)
When the hook attempts the push
Then the hook exits 0 (PostToolUse hooks cannot block)
  AND prints a warning with the failure reason to stdout
```

## Sign-offs

- [x] test-writer — 2026-05-30 14:00
- [x] python-coder — 2026-05-30 14:00
- [x] pr-reviewer — 2026-05-30 14:05
- [x] user-surface-smoker — 2026-05-30 14:10
- [x] commit — 2026-05-30 14:15
- [x] pull-request — 2026-05-30 14:15

## Comments

### 2026-05-30 14:00 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_file_created: true
  all_tests_red_before_implementation: true
  tests_cover_all_acceptance_criteria: true
Created `unit_tests/commit_guardian/test_auto_commit_inbox_ticket.py` with 16 tests covering all acceptance criteria. All tests confirmed red (FileNotFoundError — hook not yet implemented). Red baseline: all 16 tests fail with `FileNotFoundError: No such file or directory: '.../templates/hooks/auto_commit_inbox_ticket.py'`.

### 2026-05-30 14:00 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  hook_script_created: true
  hook_copied_to_dot_claude: true
  templates_settings_updated: true
  dot_claude_settings_updated: true
  decision_history_updated: true
  all_tests_pass: true
Created `templates/hooks/auto_commit_inbox_ticket.py` with all required functions. Copied to `.claude/hooks/`. Registered in both settings files. All 16 tests pass.

### 2026-05-30 14:05 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  all_acceptance_criteria_met: true
  settings_files_updated: true
  tests_pass: true
  no_contract_shrinkage: true
Reviewed implementation against all 7 Gherkin acceptance criteria — all pass. Hook correctly guards against: non-inbox paths, epic subfolders, arbitrary subdirs, already-committed files, non-main branches, linked worktrees, and push failures. Both `templates/settings.json` and `.claude/settings.json` updated. 16 tests pass. No contract shrinkage detected.

### 2026-05-30 14:10 — user-surface-smoker (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  smoke_fixture_exit_zero: true
  epic_subfolder_no_op: true
  non_inbox_path_no_op: true
  malformed_stdin_no_op: true
  placeholder_signature_absent: true
Executed smoke fixture: all scenarios exit 0. Non-inbox path, epic subfolder, and malformed stdin all produce no-op behavior. Hook output format matches assertion pattern. No `NotImplemented|TODO|pass$` placeholders found in the implementation.

### 2026-05-30 14:15 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  files_staged_explicitly: true
  commit_created: true
  no_cross_ticket_files_staged: true
Staged 4 in-scope files explicitly (templates/hooks/auto_commit_inbox_ticket.py, templates/settings.json, unit_tests/commit_guardian/test_auto_commit_inbox_ticket.py, ticket). Commit created successfully.

### 2026-05-30 14:15 — pull-request (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pr_opened: true
PR opened on origin/main with all changes from this ticket.

## Smoke Fixture

```yaml
surface: auto_commit_inbox_ticket
fixture_input: |
  {"tool_name": "Write", "tool_input": {"file_path": "tickets/00_inbox/TICKET-20260601-SmokeTest.md"}, "tool_response": {}}
assertion: "auto-commit|chore\\(tickets\\)|push.*origin|skipped|no-op"
placeholder_signature: "NotImplemented|TODO|pass$"
```

## Implementation Tasks

### python-coder

- [x] Create `templates/hooks/auto_commit_inbox_ticket.py` with the following structure:
  - Module-level docstring following the pattern in `check_ticket_rename_tracking.py`:
    MODULE, GOAL, BUSINESS CONTEXT, ARCHITECTURE, DECISION HISTORY.
  - `_is_target_path(file_path: str) -> bool`: returns True only when `file_path`
    matches `tickets/00_inbox/<name>.md` (direct child, not inside any subdirectory).
    Use `pathlib.Path` parts to check: exactly 3 parts (`tickets`, `00_inbox`, `<name>.md`),
    the name ends with `.md`, and the parent is exactly `tickets/00_inbox`. Must return
    False for `tickets/00_inbox/epics/EPIC-Foo/01_bar.md` and any deeper path.
  - `_current_branch(repo_root: Path) -> str`: runs `git -C <repo_root> rev-parse --abbrev-ref HEAD`,
    returns the branch name, returns `""` on any error.
  - `_is_worktree(repo_root: Path) -> bool`: runs `git -C <repo_root> rev-parse --git-dir`,
    checks whether the output ends with `.git` (main worktree) vs a path containing
    `.git/worktrees/` (linked worktree). Returns True when inside a linked worktree.
  - `_is_already_committed(file_path: str, repo_root: Path) -> bool`: runs
    `git -C <repo_root> status --porcelain -- <file_path>`. Returns True when stdout
    is empty (file is tracked and clean). Returns False on any error (fail-open).
  - `_run_commit_and_push(file_path: str, repo_root: Path) -> str`: runs the three-step
    sequence: `git -C <repo_root> add <file_path>`, then
    `git -C <repo_root> commit -m "chore(tickets): add <basename>"`, then
    `git -C <repo_root> push origin main`. Returns a status string: `"ok"`, `"commit_failed"`,
    or `"push_failed"`. Captures stderr and includes it in the returned string on failure.
  - `_find_repo_root(start: Path) -> Path | None`: walks up from `start` looking for a
    `.git` entry (file or directory). Returns the directory containing `.git`, or None.
  - `main() -> None`: reads stdin JSON, extracts `tool_input.file_path`, normalises to
    a relative path from repo root (strip leading absolute prefix if present), calls the
    guards in order, prints a one-line result, and exits 0 unconditionally.
  - All `subprocess.run` calls use `capture_output=True, text=True, encoding="utf-8",
    errors="replace"` and never raise on non-zero exit (use `check=False`).
  - Fail-open on malformed stdin (`json.JSONDecodeError`) or missing `file_path`.

- [x] Copy `templates/hooks/auto_commit_inbox_ticket.py` to
  `.claude/hooks/auto_commit_inbox_ticket.py` (the deployed dev-environment copy).

- [x] Register the hook in `templates/settings.json` under the existing
  `PostToolUse / Edit|Write` matcher block, alongside `ticket_frontmatter_guard.py`:
  ```json
  {
    "type": "command",
    "command": "bash -c 'd=\"$PWD\"; while [ ! -d \"$d/.claude/hooks\" ] && [ \"$d\" != \"/\" ]; do d=\"$(dirname \"$d\")\"; done; python \"$d/.claude/hooks/auto_commit_inbox_ticket.py\"'",
    "timeout": 30
  }
  ```
  Use a 30-second timeout (push can be slow on WSL2 NTFS mounts).

- [x] Apply the identical registration to `.claude/settings.json`.

- [x] Update the DECISION HISTORY block at the bottom of the hook script with a dated
  entry for this ticket.

### test-writer

- [x] Create `unit_tests/commit_guardian/test_auto_commit_inbox_ticket.py` with tests
  that invoke the hook script via `subprocess.run` (same pattern as
  `test_inline_work_guard.py`) or import the module directly where possible.

- [x] `test_target_path_direct_inbox_match`: assert `_is_target_path("tickets/00_inbox/TICKET-20260601-Foo.md")` returns True.

- [x] `test_target_path_rejects_epic_subfolder`: assert `_is_target_path("tickets/00_inbox/epics/EPIC-Foo/01_bar.md")` returns False.

- [x] `test_target_path_rejects_arbitrary_subdir`: assert `_is_target_path("tickets/00_inbox/subdir/FOO.md")` returns False.

- [x] `test_target_path_rejects_non_ticket_path`: assert `_is_target_path("docs/vision.md")` returns False.

- [x] `test_hook_no_op_on_non_inbox_path`: send stdin payload with `file_path: "docs/vision.md"`;
  assert hook exits 0 and no git subprocess was invoked.

- [x] `test_hook_no_op_on_epic_subfolder`: send payload with
  `file_path: "tickets/00_inbox/epics/EPIC-Foo/01_bar.md"`; assert exits 0, no git ops.

- [x] `test_hook_no_op_when_already_committed`: mock `_is_already_committed` to return True;
  assert exits 0 without calling `_run_commit_and_push`.

- [x] `test_hook_no_op_when_branch_not_main`: mock `_current_branch` to return `"feature/x"`;
  assert exits 0 without push, prints "skipped" or "not main".

- [x] `test_hook_no_op_in_worktree`: mock `_is_worktree` to return True;
  assert exits 0 without push.

- [x] `test_hook_happy_path_commits_and_pushes`: mock `_is_already_committed` → False,
  `_current_branch` → "main", `_is_worktree` → False, `_run_commit_and_push` → "ok";
  assert exits 0 and confirmation output contains the basename.

- [x] `test_hook_push_failure_is_nonfatal`: mock `_run_commit_and_push` → "push_failed: permission denied";
  assert exits 0 and warning appears in stdout.

- [x] `test_hook_fail_open_on_malformed_stdin`: send `"{broken json"` as stdin;
  assert exits 0 without raising.

## Risk & Safety

- Touches money? No.
- Touches data? No — only ticket definition files.
- Reversibility? Fully reversible. `git revert` or `git push --force-with-lease` can
  undo any auto-pushed ticket commit. The hook can be disabled by removing its entry
  from `settings.json` and rebuilding.
- Shared contract: adds a new entry to the `PostToolUse / Edit|Write` hook chain in
  `settings.json`. Existing hooks are unaffected. The new hook is additive and
  unconditionally exits 0 (PostToolUse hooks cannot block tool execution).
- Worktree safety: the `_is_worktree` guard prevents push from linked worktrees.
  Without it, a ticket written during an epic drive from a worktree would push to
  `main` from a feature context, bypassing PR review for that file.
- Push scope: `git push origin main` pushes the entire `main` branch, not just the
  new file. This is safe for inbox tickets (they are always additive) but means any
  other uncommitted local changes on `main` would also be pushed if present. The
  `_is_already_committed` guard and the branch guard together ensure we only push
  when on a clean `main` with a single new file staged. Note: the hook does not
  verify that `main` has no other staged changes — the `python-coder` should document
  this as a known limitation in the module docstring.
- Timeout: 30 seconds covers WSL2 NTFS + SSH push latency. If the push stalls
  beyond that, Claude Code will kill the hook process (exit 0 via SIGTERM, non-blocking).
