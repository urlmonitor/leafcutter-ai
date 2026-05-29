---
title: "Add PostToolUse hook to auto-commit and push standalone inbox tickets to main"
status: todo
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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  sql-query: not_needed
  frontend-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  pr-reviewer: needed
  user-surface-smoker: needed
  commit: needed
  pull-request: needed
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

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] user-surface-smoker
- [ ] commit
- [ ] pull-request

## Comments

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

- [ ] Create `templates/hooks/auto_commit_inbox_ticket.py` with the following structure:
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

- [ ] Copy `templates/hooks/auto_commit_inbox_ticket.py` to
  `.claude/hooks/auto_commit_inbox_ticket.py` (the deployed dev-environment copy).

- [ ] Register the hook in `templates/settings.json` under the existing
  `PostToolUse / Edit|Write` matcher block, alongside `ticket_frontmatter_guard.py`:
  ```json
  {
    "type": "command",
    "command": "bash -c 'd=\"$PWD\"; while [ ! -d \"$d/.claude/hooks\" ] && [ \"$d\" != \"/\" ]; do d=\"$(dirname \"$d\")\"; done; python \"$d/.claude/hooks/auto_commit_inbox_ticket.py\"'",
    "timeout": 30
  }
  ```
  Use a 30-second timeout (push can be slow on WSL2 NTFS mounts).

- [ ] Apply the identical registration to `.claude/settings.json`.

- [ ] Update the DECISION HISTORY block at the bottom of the hook script with a dated
  entry for this ticket.

### test-writer

- [ ] Create `unit_tests/commit_guardian/test_auto_commit_inbox_ticket.py` with tests
  that invoke the hook script via `subprocess.run` (same pattern as
  `test_inline_work_guard.py`) or import the module directly where possible.

- [ ] `test_target_path_direct_inbox_match`: assert `_is_target_path("tickets/00_inbox/TICKET-20260601-Foo.md")` returns True.

- [ ] `test_target_path_rejects_epic_subfolder`: assert `_is_target_path("tickets/00_inbox/epics/EPIC-Foo/01_bar.md")` returns False.

- [ ] `test_target_path_rejects_arbitrary_subdir`: assert `_is_target_path("tickets/00_inbox/subdir/FOO.md")` returns False.

- [ ] `test_target_path_rejects_non_ticket_path`: assert `_is_target_path("docs/vision.md")` returns False.

- [ ] `test_hook_no_op_on_non_inbox_path`: send stdin payload with `file_path: "docs/vision.md"`;
  assert hook exits 0 and no git subprocess was invoked.

- [ ] `test_hook_no_op_on_epic_subfolder`: send payload with
  `file_path: "tickets/00_inbox/epics/EPIC-Foo/01_bar.md"`; assert exits 0, no git ops.

- [ ] `test_hook_no_op_when_already_committed`: mock `_is_already_committed` to return True;
  assert exits 0 without calling `_run_commit_and_push`.

- [ ] `test_hook_no_op_when_branch_not_main`: mock `_current_branch` to return `"feature/x"`;
  assert exits 0 without push, prints "skipped" or "not main".

- [ ] `test_hook_no_op_in_worktree`: mock `_is_worktree` to return True;
  assert exits 0 without push.

- [ ] `test_hook_happy_path_commits_and_pushes`: mock `_is_already_committed` → False,
  `_current_branch` → "main", `_is_worktree` → False, `_run_commit_and_push` → "ok";
  assert exits 0 and confirmation output contains the basename.

- [ ] `test_hook_push_failure_is_nonfatal`: mock `_run_commit_and_push` → "push_failed: permission denied";
  assert exits 0 and warning appears in stdout.

- [ ] `test_hook_fail_open_on_malformed_stdin`: send `"{broken json"` as stdin;
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
