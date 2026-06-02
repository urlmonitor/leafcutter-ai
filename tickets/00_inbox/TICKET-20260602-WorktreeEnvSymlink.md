---
title: "Symlink .env into worktrees instead of copying it"
status: todo
components:
  - build_pipeline
created: 2026-06-02
depends_on: []
priority: medium
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
---

# Symlink .env into worktrees instead of copying it

## Actor / Goal

In order to keep environment variables in sync across all worktrees, we need
`_bootstrap()` in `setup_ticket_worktree.py` to create a symlink from the
worktree's `.env` back to the main repo's `.env`, so that changes to the main
`.env` are automatically picked up by all worktrees without a manual re-copy.

## Context

`_bootstrap()` currently copies `.env` from the main repo into each new
worktree using `shutil.copy`. This means:

1. When `.env` is updated in the main repo, every existing worktree is stale
   and agents or scripts inside them that read environment variables see the
   old values.
2. The gap causes silent failures that are hard to diagnose — the worktree
   starts up with an outdated API key, DB URL, or flag, and the only clue is
   a connection error or a wrong-env behaviour rather than a missing-file error.

The canonical fix is to replace the `.env` copy with `os.symlink(src, dst)`.
A symlink is a one-liner change and solves the sync problem permanently because
the worktree file system entry resolves to the main repo's inode at every read.

`.mcp.json` should remain a copy because its content is set once at bootstrap
time and is not expected to change after the worktree is created.

### Architectural context

`_bootstrap()` lives in `templates/scripts/setup_ticket_worktree.py` and is
called by both subcommands (`setup-ticket` and `create-only`). The file is
deployed to adopter projects via the leafcutter build pipeline (`build_pipeline`
component). The change is fully contained within this one function; no other
module boundary is crossed.

Platform note: on Windows without Developer Mode or UAC elevation,
`os.symlink` raises `OSError: [WinError 1314] A required privilege is not
held by the client`. The implementation must catch this specific error and
fall back to `shutil.copy` with a warning to stderr, preserving the existing
behaviour on constrained Windows environments while giving the symlink
experience on Linux/macOS/WSL2.

## Acceptance Criteria

```gherkin
Given setup_ticket_worktree.py _bootstrap() is called on Linux/macOS/WSL2
When the main_repo/.env file exists
Then worktree/.env is a symlink pointing to main_repo/.env
And reading worktree/.env after updating main_repo/.env returns the new content

Given setup_ticket_worktree.py _bootstrap() is called
When main_repo/.env does not exist
Then no symlink is created and no error is raised

Given setup_ticket_worktree.py _bootstrap() is called on Windows without symlink privilege
When os.symlink raises OSError (WinError 1314 or EPERM)
Then _bootstrap() falls back to shutil.copy for .env and prints a warning to stderr

Given setup_ticket_worktree.py _bootstrap() is called
When main_repo/.mcp.json exists
Then worktree/.mcp.json is a file copy (not a symlink) as before
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

- [ ] In `_bootstrap()`, replace the `shutil.copy(src, dst)` call for `.env`
  with `os.symlink(src, dst)`. The `os` module is already in stdlib — no new
  import needed.
- [ ] Wrap the `os.symlink` call in a `try/except OSError` block. On `OSError`
  (covers `WinError 1314` and `EPERM`), print a warning to stderr and fall back
  to `shutil.copy(src, dst)` so the function still produces a usable `.env` on
  restricted Windows environments.
- [ ] Keep `shutil.copy` for `.mcp.json` unchanged (only `.env` gets the
  symlink treatment).
- [ ] Update the DECISION HISTORY block at the bottom of
  `templates/scripts/setup_ticket_worktree.py` with a dated entry recording
  the symlink policy change and referencing this ticket.
- [ ] Update the module-level docstring line that reads "`.env` copy policy"
  to reflect the new symlink-first behaviour.

### test-writer

- [ ] Create (or extend) `tests/test_setup_ticket_worktree.py`.
- [ ] `test_bootstrap_env_is_symlinked`: mock `os.symlink` and confirm it is
  called with `(main_repo/.env, worktree/.env)` when the source exists;
  confirm `shutil.copy` is NOT called for `.env`.
- [ ] `test_bootstrap_env_symlink_skipped_when_missing`: patch `os.symlink` to
  raise `FileNotFoundError`; confirm no exception propagates and no `.env`
  symlink/copy is created.
- [ ] `test_bootstrap_env_fallback_on_oserror`: patch `os.symlink` to raise
  `OSError`; confirm `shutil.copy` is called as fallback and a warning is
  printed to stderr.
- [ ] `test_bootstrap_mcp_json_still_copied`: confirm `shutil.copy` is called
  for `.mcp.json` regardless of the `.env` symlink path.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The change is to one function in one template file. Reverting
  is a one-line revert. Existing worktrees already created with a copy of `.env`
  are unaffected — they keep their copy; only new worktrees get the symlink.
- Platform risk: Windows symlink privilege. Mitigated by the OSError fallback
  described above. WSL2 (the primary dev environment per CLAUDE.md OS note) has
  no symlink restrictions.
- If the main repo `.env` is deleted after worktree creation, the symlink
  becomes a dangling link. This is acceptable and already the case with the
  copy approach (deleted file = missing copy). The symlink makes the problem
  visible immediately rather than silently serving stale content.
