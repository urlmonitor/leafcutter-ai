---
title: "check-folder-density refuses merge commits for folders that grew dense on the merged-in branch"
status: done
components:
  - commit_guardian
created: 2026-10-10
last_updated: 2026-10-10
depends_on: []
priority: high
roadmap_phase: phase_1
change_target: infrastructure
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# check-folder-density refuses merge commits for folders that grew dense on the merged-in branch

## Actor / Goal
In order for a branch to take in main without a hook skip, the folder-density hook must treat folders that are already dense on the merged-in branch as pre-existing.

## Context
- **Found:** 2026-10-10. Merging `origin/main` into `docs/pol-git-001` (#990, 492 commits behind) and `acs/decision-lifecycle` (#1004, 377 behind) was refused for 30 and 7 folders respectively, none touched by either PR (e.g. `unit_tests/suite_performance/` 74 files, the DK-200..DK-500 AC folders, `kernel/`, `scripts/ci/`). Both merges needed a user-run `SKIP=check-folder-density` commit.
- **Cause:** `templates/scripts/commit_guardian/check_folder_density.py` reads the BEFORE snapshot from `git ls-tree -r HEAD` only. In a merge, HEAD is the branch's old tip, so every folder that crossed the limit on main since the branch point counts as "newly dense in this commit". Armed to refuse on 2026-10-08 (`d8cd00a9d`, GE-120h-3).

## Scope
1. When `MERGE_HEAD` exists, a folder counts as pre-existing when it is already over the limit in HEAD **or** in MERGE_HEAD (each parent's tree); only a folder the merge result itself pushes over the limit is a violation.
2. Tests: a merge bringing in an already-dense folder passes; a merge that makes a folder newly dense in neither parent but dense in the result is refused; a normal commit is unchanged.
3. Mirror `templates/` → `scripts/` through the build.

## Out of Scope
- Changing the limit or the exemptions.

## Sign-offs

- [x] test-writer — 2026-10-12 12:00
- [x] python-coder — 2026-10-12 13:00
- [x] pr-reviewer — 2026-10-12 07:15
- [x] commit — 2026-10-12 14:30
- [x] pull-request — 2026-10-12 14:45

## Comments

### 2026-10-12 12:00 — test-writer (status: ok)
feedback-id: fb_2026-10-12_5a8fb652
Wrote unit_tests/commit_guardian/test_folder_density_merge_commit.py (5 tests, real git merge --no-commit state, driven via run_hook.py).
red_baseline:
  - test_name: test_merge_bringing_in_already_dense_folder_passes
    file: unit_tests/commit_guardian/test_folder_density_merge_commit.py
    kind: assertion
    error: "AssertionError: 'FOLDER TOO DENSE' unexpectedly found ... FOLDER TOO DENSE: X/ Non-markdown files: 18 (limit: 15)"
Green already (pre-existing behaviour, regression guards): dense-only-in-result refused (Y), 16th file refused, over-limit-in-HEAD warns, no leak for unmerged-branch folder.
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: real git merge state (MERGE_HEAD, index)
    consuming_side: check_folder_density.py via run_hook.py
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python templates/scripts/commit_guardian/run_hook.py check_folder_density.py (hook runner via subprocess)"

### 2026-10-12 13:00 — python-coder (status: ok)
feedback-id: fb_2026-10-12_eff19988
Added templates/scripts/commit_guardian/_density_parents.py (reads MERGE_HEAD shas via `git rev-parse --git-path`, ls-tree per parent) and wired it into check_folder_density.py main(): before_counts[folder] = max over HEAD and every MERGE_HEAD parent. No MERGE_HEAD => unchanged. check_folder_density.py is 390 lines.
red_baseline_results:
  - test_name: test_merge_bringing_in_already_dense_folder_passes
    result: green
New module 5/5 green. test_ge_120h_3*.py: 12 failed/6 passed/4 errors, identical to the pre-change baseline (local Windows cp1252 harness failures, not caused by this change).

### 2026-10-12 07:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-12_df6ee9b4
No high or medium findings. Verified: max-over-parents BEFORE (incl. octopus: all MERGE_HEAD lines iterated); git call failures re-raise uncaught, fail-closed like get_all_tracked_files; new calls carry encoding=utf-8; `git rev-parse --git-path MERGE_HEAD` resolves to the per-worktree gitdir in a linked worktree (absolute) and is cwd-relative in a plain repo, read from the same cwd so subdirs work; deployed .leafcutter copy is identical, in the build manifest, and importable (script dir on sys.path). 5/5 tests pass.
Low (suppressed, optional): over-long comment line before before_counts in check_folder_density.py; no test drives a linked worktree or an octopus merge.

### 2026-10-12 14:30 — commit (status: ok)
feedback-id: fb_2026-10-12_cc938d86
Auto-authorized commit gate: subject "fix(commit-guardian): folder-density counts folders already dense in any merge parent as pre-existing"; staged files: changelog entry, _density_parents.py, check_folder_density.py, this ticket, test_folder_density_merge_commit.py.
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

### 2026-10-12 14:45 — pull-request (status: ok)
feedback-id: fb_2026-10-12_0ce9bb2b
Opened https://github.com/urlmonitor/leafcutter-ai/pull/1143 from fix/folder-density-merge-commit (399875bb7) into main; body lists the change, ticket, known issue and test plan. Merge awaits CI and the user's approval.
completion_manifest:
  pr_opened: true
  pr_body_has_test_plan: true
