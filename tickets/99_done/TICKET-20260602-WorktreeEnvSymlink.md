---
title: "Symlink .env into worktrees instead of copying it"
status: done
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
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] architect-review — 2026-06-02 14:00
- [x] test-writer — 2026-06-03 08:00
- [x] python-coder — 2026-06-03 08:30
- [x] test-runner — 2026-06-03 09:00
- [x] pr-reviewer — 2026-06-03 09:15
- [x] commit — 2026-06-03 09:30
- [x] pull-request — 2026-06-03 09:45

## Comments

### 2026-06-02 14:00 — architect-review (status: ok)
feedback-id: fb_2026-06-02_2f5a6dff
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

Architectural review complete. Impact classification: **small**. The change is entirely contained within `_bootstrap()` in `templates/scripts/setup_ticket_worktree.py` — 2 files, 1 component (`build_pipeline`), no always-large triggers (no Alembic migration, no hypertable change, no public API change, no ADR contract change). Design is sound: `os.symlink` with `OSError` fallback to `shutil.copy` correctly handles the Windows privilege case while improving sync semantics on Linux/macOS/WSL2. `requires_adr: false` is correct — this is a narrow, single-component implementation detail with no new cross-cutting policy. No suggested diagrams (pure refactor within one function, no new boundary). Handoff to test-writer and python-coder.

### 2026-06-03 08:00 — test-writer (status: ok)
feedback-id: fb_2026-06-03_91f5cb0c
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true

Created `tests/test_setup_ticket_worktree.py` with 4 tests. Red baseline: 3 FAILED, 1 PASSED. `test_bootstrap_env_is_symlinked` fails because `_bootstrap()` currently calls `shutil.copy` not `os.symlink` for `.env`. `test_bootstrap_env_symlink_skipped_when_missing` fails because the current code always calls `shutil.copy` even when FileNotFoundError is raised by symlink (the current except branch catches FileNotFoundError and does nothing, but the test expects no shutil.copy call). `test_bootstrap_env_fallback_on_oserror` fails because OSError is not caught (it propagates) and no stderr warning is printed. `test_bootstrap_mcp_json_still_copied` is GREEN — the existing copy for `.mcp.json` is already correct. Red baseline confirmed. Python-coder must make the 3 failing tests green.

### 2026-06-03 08:30 — python-coder (status: ok)
feedback-id: fb_2026-06-03_31fcd3fa
completion_manifest:
  implementation_complete: true
  tests_green: true
  decision_history_updated: true
  docstring_updated: true

Replaced `shutil.copy` for `.env` with `os.symlink` in `_bootstrap()`. Added `try/except OSError` fallback to `shutil.copy` with stderr warning for Windows environments without symlink privilege. `.mcp.json` remains a plain copy. Updated module docstring (`".env` copy policy"` → `".env symlink policy"`) and DECISION HISTORY block with dated entry referencing TICKET-20260602-WorktreeEnvSymlink. All 4 tests GREEN: `test_bootstrap_env_is_symlinked`, `test_bootstrap_env_symlink_skipped_when_missing`, `test_bootstrap_env_fallback_on_oserror`, `test_bootstrap_mcp_json_still_copied`.

### 2026-06-03 09:00 — test-runner (status: ok)
feedback-id: fb_2026-06-03_1d635a02
completion_manifest:
  tests_all_passed: true
  regressions_checked: true

4/4 target tests pass (`tests/test_setup_ticket_worktree.py`). Broader suite shows 1 pre-existing failure in `test_emit_entry_cwd.py::TestEmitEntryCwdIndependence::test_explicit_relative_changelog_dir_resolves_against_repo_root` — confirmed pre-existing by running against the clean branch (same failure). No regressions introduced by this change.

### 2026-06-03 09:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_f44f3dbd
completion_manifest:
  acceptance_criteria_met: true
  error_handling_compliant: true
  tests_reviewed: true
  diff_reviewed: true

Implementation approved. All 4 acceptance criteria met per gherkin spec. Error handling follows project CLAUDE.md rules: `os.symlink` wrapped in `try/except OSError` (Rule 1), no bare excepts (Rule 2), `OSError` logs warning to stderr (Rule 3), `FileNotFoundError` silently skipped — consistent with existing project pattern and ticket spec ("missing files silently skipped"). No new imports needed. DECISION HISTORY entry is complete and correctly references the ticket. 4 tests green with no regressions in the broader suite.

### 2026-06-03 09:30 — commit (status: ok)
feedback-id: fb_2026-06-03_f698579b
completion_manifest:
  files_staged_explicitly: true
  commit_created: true
  pre_commit_hooks_passed: true

Staged 4 files explicitly: `templates/scripts/setup_ticket_worktree.py`, `tests/test_setup_ticket_worktree.py`, `tickets/00_inbox/TICKET-20260602-WorktreeEnvSymlink.md` (deleted), `tickets/01_todo/TICKET-20260602-WorktreeEnvSymlink.md`. Pre-commit hooks passed. Commit `d104a06` created on `feature/worktreeenvsymlink`.

### 2026-06-03 09:45 — pull-request (status: ok)
feedback-id: fb_2026-06-03_ffe5ef7c
completion_manifest:
  branch_pushed: true
  pr_created: true

Branch `feature/worktreeenvsymlink` pushed to origin. PR opened: https://github.com/urlmonitor/leafcutter-ai/pull/33

```json
{
  "architectural_note": "Change is fully contained within _bootstrap() in templates/scripts/setup_ticket_worktree.py. Single component (build_pipeline), 2 files, no always-large triggers. The os.symlink + OSError fallback pattern is idiomatic Python and the ticket's platform note correctly identifies the WinError 1314 case. No ADR needed — this is an implementation detail within an existing function, not a new cross-cutting policy.",
  "acceptance_adjustments": [],
  "escalation": "none",
  "escalation_reason": "",
  "suggested_adr": null,
  "suggested_diagrams": []
}
```

## Escalation

Branch: none
Reason: 2 files in one component (build_pipeline); no always-large trigger fired; threshold criteria all met for small classification.

## Implementation Tasks

### python-coder

- [x] In `_bootstrap()`, replace the `shutil.copy(src, dst)` call for `.env`
  with `os.symlink(src, dst)`. The `os` module is already in stdlib — no new
  import needed.
- [x] Wrap the `os.symlink` call in a `try/except OSError` block. On `OSError`
  (covers `WinError 1314` and `EPERM`), print a warning to stderr and fall back
  to `shutil.copy(src, dst)` so the function still produces a usable `.env` on
  restricted Windows environments.
- [x] Keep `shutil.copy` for `.mcp.json` unchanged (only `.env` gets the
  symlink treatment).
- [x] Update the DECISION HISTORY block at the bottom of
  `templates/scripts/setup_ticket_worktree.py` with a dated entry recording
  the symlink policy change and referencing this ticket.
- [x] Update the module-level docstring line that reads "`.env` copy policy"
  to reflect the new symlink-first behaviour.

### test-writer

- [x] Create (or extend) `tests/test_setup_ticket_worktree.py`.
- [x] `test_bootstrap_env_is_symlinked`: mock `os.symlink` and confirm it is
  called with `(main_repo/.env, worktree/.env)` when the source exists;
  confirm `shutil.copy` is NOT called for `.env`.
- [x] `test_bootstrap_env_symlink_skipped_when_missing`: patch `os.symlink` to
  raise `FileNotFoundError`; confirm no exception propagates and no `.env`
  symlink/copy is created.
- [x] `test_bootstrap_env_fallback_on_oserror`: patch `os.symlink` to raise
  `OSError`; confirm `shutil.copy` is called as fallback and a warning is
  printed to stderr.
- [x] `test_bootstrap_mcp_json_still_copied`: confirm `shutil.copy` is called
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
