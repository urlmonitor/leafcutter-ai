---
title: "KI-CG-20260927-file-size-hook-read-another-worktrees-index — check-file-size once measured the staged files of a different worktree, while every other hook in the same run saw the right ones"
description: "high — during a commit in one worktree, check-file-size refused three files that were staged in another session's worktree and not in the committing one; the other hooks of the same run inspected the correct staged set. It did not reproduce on a direct run or on the retry, so the cause is unknown. Observed failing closed; the same misread could let an oversized file through."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
  - docs/analysis/2026-09-25-worktree-failure-modes.md
---

# KI-CG-20260927-file-size-hook-read-another-worktrees-index — check-file-size measured another worktree's staged files

- **Severity:** high. Observed failing closed: it blocked a valid commit. The same misread
  could pass a commit whose own oversized files it never looked at. The cause is unexplained,
  and the hook's output does not say which checkout it inspected, so a wrong read cannot be
  told apart from a right one.
- **Status:** open, no AC. Seen once on 2026-09-25. It did not reproduce on a direct run or on
  the retry.
- **Where:** `templates/scripts/commit_guardian/check_file_size.py` lists the staged files with
  a bare `git diff --cached --name-status` (no `-C`, no explicit root), and runs through
  `run_hook.py`. In a worktree with no main `.venv`, `run_hook.py` falls back to
  `poetry run python`.

## Symptom

The worktree `worktrees/ac-workspace-component` (branch `ac-authoring/workspace-component`)
had 69 AC YAML files staged and nothing else. Its commit was refused by `check-file-size` for
three files it had not touched:

- `templates/workflows-js/plan-feature.js`, "grew while already over its limit" (2918 to 3077)
- `unit_tests/_workflow_engine_harness.py` (757 to 921)
- `unit_tests/test_workflow_dual_engine.py` (949 to 984)

The same run reported two new files it had "checked": `unit_tests/workflows/test_bo_1500a_5_i.py`
and `test_bo_2300a_1_ii.py`.

All five were staged in a different session's worktree, `worktrees/plan-feature-bootstrap-fail-closed`,
and none existed as changes in the committing worktree. In the same hook run, `check-ac-schema`
reported a finding on one of the committing worktree's own YAML files, so the other hooks were
reading the right staged set.

## What was ruled out

- **The committing environment.** On the retry, `env | grep '^GIT_'` showed only
  `GIT_EDITOR=true`: no `GIT_DIR`, `GIT_WORK_TREE` or `GIT_INDEX_FILE` override. The working
  directory was the worktree root.
- **A persistent misconfiguration.** Run directly from the committing worktree, through
  `run_hook.py`, the hook listed the correct staged set (YAML only, out of scope) and passed.
  The retried commit passed `check-file-size` too.

## Candidate mechanisms (unverified)

1. The `poetry run python` fallback in `run_hook.py` resolves the interpreter, and possibly the
   working directory, from a project other than the committing worktree while another worktree
   is active.
2. The two sessions committed at about the same time, and something shared between worktrees
   (the common `.git` directory, the shared `.git/hooks/pre-commit`, or pre-commit's cache) let
   one run pick up the other's state.
3. Any cwd-dependent step in the hook, the same class as KI-CG-20260901 and cluster C4/C5 of the
   duplication analysis (about 45 private `git diff --cached` queries, each resolving its
   checkout implicitly).

## Fix direction

- Resolve the checkout once, explicitly, and run every git query with `-C <that root>`. Use the
  shared change-set reader that cluster C5 proposes, not a private `git diff --cached`.
- Print the inspected checkout's root and branch on the hook's RESULT line, so that a read of
  the wrong index is visible in the output instead of looking like an ordinary refusal.
- Fail closed with a named error when a file reported as staged does not exist in the inspected
  worktree. That would have turned this incident into a self-describing failure.
- To reproduce: two worktrees of the same repository, each with different staged content, both
  committing at the same time, with no main `.venv` (so the poetry fallback is active).
