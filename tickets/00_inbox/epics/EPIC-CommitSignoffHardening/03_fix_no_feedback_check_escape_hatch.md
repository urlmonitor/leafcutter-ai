---
title: "Fix [NO-FEEDBACK-CHECK] escape hatch: detect at pre-commit stage"
status: todo
components:
  - build_system
created: 2026-05-22
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - scripts/commit_guardian/check_feedback_id.py
agents:
  architect-review: not_needed
  python-coder: signed_off
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  test-writer: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  sql-coder: not_needed
  user-surface-smoker: not_needed
---

# 03: Fix [NO-FEEDBACK-CHECK] escape hatch — detect at pre-commit stage

## Actor / Goal

In order to bypass the feedback-id check without having to inline-synthesize feedback-id lines, users need `[NO-FEEDBACK-CHECK]` in the commit message to suppress `check_feedback_id` at the pre-commit stage, not only at the commit-msg stage.

## Context

Feedback ID: fb_2026-05-17_3af4c531.

`check_feedback_id.py` has an escape hatch — if `[NO-FEEDBACK-CHECK]` appears in the commit message, all feedback-id checks are skipped. However, the escape hatch only works at the **commit-msg** hook stage. At the **pre-commit** stage (which runs earlier), `COMMIT_EDITMSG` does not yet exist, so the token cannot be read from it.

The result: a user who writes `git commit -m "fix: something [NO-FEEDBACK-CHECK]"` gets blocked by `check_feedback_id` at pre-commit, adds feedback-id lines by hand (or uses precommit-autofix), and then the escape hatch kicks in at commit-msg — by which point the workaround was already done. The escape hatch is effectively broken for the primary use case.

Reading `check_feedback_id.py` (lines 61–126): the `_should_skip()` function already tries four sources for the commit message, including `git rev-parse --git-dir` + `COMMIT_EDITMSG`. The fourth source (the `git rev-parse` path) should work at pre-commit time — git writes to `COMMIT_EDITMSG` before running pre-commit hooks. The bug is likely that `COMMIT_EDITMSG` is written by git but the path resolution fails in practice (worktree nesting, Windows path separator, or env var not set), so the fourth source silently falls through.

## Acceptance Criteria

```gherkin
Given a staged diff contains a ticket comment heading without a feedback-id line
When the user runs git commit -m "fix: something [NO-FEEDBACK-CHECK]"
Then check_feedback_id exits 0 at the pre-commit stage
And the commit proceeds without requiring inline feedback-id lines

Given the escape hatch token is NOT in the commit message
When a staged diff contains a comment heading without feedback-id
Then check_feedback_id exits 1 at the pre-commit stage (existing behaviour preserved)

Given a git worktree (not the main working tree)
When the user uses [NO-FEEDBACK-CHECK] in the commit message
Then the escape hatch is still detected correctly (worktree COMMIT_EDITMSG path resolution works)
```

## Sign-offs

- [x] python-coder — 2026-05-22 10:00
- [x] test-writer — 2026-05-22 10:00
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-22 10:00 — python-coder (status: ok)

feedback-id: fb_2026-05-22_0f069cf3
Fixed `_should_skip()` in `scripts/commit_guardian/check_feedback_id.py` by adding `.resolve()` to the fourth source path construction so relative gitdir paths (returned by `git rev-parse --git-dir` in worktrees) are converted to absolute paths before `.exists()` is called. Added a fifth source that scans `sys.argv` for positional args pointing to commit-msg files. Updated the DECISION HISTORY to document the 2026-05-22 fix.

### 2026-05-22 10:00 — test-writer (status: ok)

feedback-id: fb_2026-05-22_f228aa45
Created `tests/test_check_feedback_id.py` with 11 unit tests covering: escape token in commit-msg file, no token in file, None arg (fail-open), absolute gitdir with/without token, relative gitdir path resolution, worktree path layout (`.git/worktrees/<branch>/COMMIT_EDITMSG`), git failure handling, missing COMMIT_EDITMSG, and GIT_COMMIT_MSG/COMMIT_EDITMSG env vars. All 11 tests pass.

## Implementation Tasks

### python-coder
- [x] Add debug instrumentation to `_should_skip()` to log which source is being checked and what value is found. Run `git commit -m "test [NO-FEEDBACK-CHECK]"` in a scratch branch with a staged heading-without-feedback-id and confirm whether the fourth source (git rev-parse path) resolves correctly on Windows/worktree.
- [x] Fix the path resolution bug (likely: `Path(git_dir) / "COMMIT_EDITMSG"` resolves to the worktree's gitdir, but on Windows the path separator or drive letter differs). Ensure the resolved path is absolute before checking `exists()`.
- [x] Add a fifth source: check `sys.argv` for `--commit-msg-file` (pre-commit framework may pass it as a positional arg to the hook at commit-msg stage but not pre-commit stage; if absent, fall back to the existing four sources).
- [x] If `git commit -m <msg>` is used, git writes the message to `COMMIT_EDITMSG` before pre-commit runs. Verify this is true on the platform (it is per git documentation; add a comment citing the git source if needed).
- [x] Ensure the fix does NOT open a security hole (e.g. reading from an arbitrary env-var path).

### test-writer
- [x] Write a unit test in `unit_tests/commit_guardian/` that mocks `git rev-parse --git-dir` output and a fake `COMMIT_EDITMSG` containing `[NO-FEEDBACK-CHECK]`, then asserts `_should_skip()` returns `True`.
- [x] Write a second test without the token in `COMMIT_EDITMSG` asserting `_should_skip()` returns `False`.
- [x] Write a worktree-path test: `COMMIT_EDITMSG` is at `.git/worktrees/<branch>/COMMIT_EDITMSG` — assert the resolution still works.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The change is in one function in `check_feedback_id.py`. Revert by restoring the file.
- Security: the escape hatch suppresses the feedback-id check for the entire commit. It must NOT be triggered by env vars an attacker could set in CI — only by the commit message content.
