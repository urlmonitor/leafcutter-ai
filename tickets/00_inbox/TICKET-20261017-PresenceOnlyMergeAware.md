---
title: "check-presence-only-assertions refuses merge commits for tests the merged-in branch added"
status: todo
components:
  - commit_guardian
created: 2026-10-17
last_updated: 2026-10-17
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
  commit: needed
  pull-request: needed
---

# check-presence-only-assertions refuses merge commits for tests the merged-in branch added

## Actor / Goal
In order for a branch to take in main with every check judging the merge, the presence-only-assertion hook must judge only what the merge itself adds, not every line the merged-in branch brought.

## Context
- **Found:** 2026-10-17, merging `origin/main` (816feef05, 260 commits) into `epic/every-piece-of-separate-work-gets-its-workspace` (BO-4300). The hook refused two of main's own tests, `unit_tests/ac_driven_dev/rule_check/test_acd_2500a_1.py` and `test_acd_2500a_1_review_g2_workflow.py`. Both are byte-identical to main and their presence-only lines were already judged when they landed on main. The user chose to fix the hook first rather than skip it.
- **Cause:** `templates/scripts/commit_guardian/check_presence_only_assertions.py` reads `git diff --cached` (against HEAD only). In a merge, HEAD is the branch's old tip, so every line main added since the branch point reads as added by this commit.
- **Precedent:** the same merge misattribution was fixed for check-folder-density (TICKET-20261010-FolderDensityMergeCommit, #1143), for check-file-size (max over parents), and for check-package-surface-declaration. The shared merge-scoping source is `templates/scripts/commit_guardian/_authored_change.py` (GE-120e-1), which check-contract-shrinking and the frontmatter validators use.

## Scope
1. During a merge (or revert or cherry-pick), the hook judges the authored change from `_authored_change.get_authored_change()`, the same source the other merge-aware checks use, instead of a bare `git diff --cached`. A plain commit is unchanged. A could-not-check result stays could-not-check, never a pass on the unscoped diff.
2. Tests, run against real temporary git repositories with no git mocks:
   - a merge that brings in a presence-only assertion added on the merged-in branch passes;
   - a merge whose own resolution adds a presence-only assertion is refused;
   - a plain commit adding one is still refused.
3. Mirror `templates/` → `scripts/` through the build.

## Out of Scope
- What counts as a presence-only assertion, and the scanned-source list.
- check-contract-shrinking's own merge rule (GE-120e-1 deliberately counts the branch's earlier work there).

## Test Requirements

```yaml
tests:
- name: test_merge_bringing_in_branch_added_presence_only_assertion_passes
  file: unit_tests/commit_guardian/test_presence_only_merge_aware.py
  asserts: In a real repo with MERGE_HEAD set, a presence-only assertion that exists only because the merged-in branch added it is not refused.
  framework: unittest
  type: behavioral
- name: test_merge_resolution_adding_presence_only_assertion_is_refused
  file: unit_tests/commit_guardian/test_presence_only_merge_aware.py
  asserts: A presence-only assertion that is in neither parent but in the merge result is refused.
  framework: unittest
  type: behavioral
- name: test_plain_commit_adding_presence_only_assertion_still_refused
  file: unit_tests/commit_guardian/test_presence_only_merge_aware.py
  asserts: With no operation in progress, an added presence-only assertion is refused as before.
  framework: unittest
  type: behavioral
```

## Sign-offs

- [x] test-writer — 2026-10-17 09:31
- [x] python-coder — 2026-10-17 10:05
- [x] pr-reviewer — 2026-10-17 09:35
- [ ] commit
- [ ] pull-request

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-17 09:31 — test-writer (status: ok)
feedback-id: fb_2026-10-17_7ee77228
Wrote unit_tests/commit_guardian/test_presence_only_merge_aware.py (3 tests, real temp git repos, real hook subprocess, no git mocks). Verification: `python -m pytest unit_tests/commit_guardian/test_presence_only_merge_aware.py -q` -> 1 failed, 2 passed. Tests 2 and 3 are green guards by design. cross_layer_seam_answer: covered (hook reads real git state produced by real merges). reachability_entry_point_answer: resolved, CLI via subprocess of check_presence_only_assertions.py.
red_baseline:
  - test_name: test_merge_bringing_in_branch_added_presence_only_assertion_passes
    file: unit_tests/commit_guardian/test_presence_only_merge_aware.py
    kind: assertion
    error: "AssertionError: 1 != 0 : carried-in assertion must not be judged on the merge; stdout=BLOCKED - presence-only assertion(s) added over scanned source ... unit_tests/commit_guardian/test_added_presence_only.py ... 'compute_thing('"

### 2026-10-17 10:05 — python-coder (status: ok)
feedback-id: fb_2026-10-17_7121fb69
check_presence_only_assertions.py now takes its diff from the shared `_authored_change.get_authored_change()` during a merge/revert/cherry-pick (plain commit, HOOK_TEST_DIFF seam and missing-module fallback keep the bare `git diff --cached`). A could-not-check derivation (in-band or raised) prints a warning, emits `RESULT: could_not_check` via check_outcome (ImportError fallback included) and returns 0, never widening to the unscoped diff. Verification: build ok; `AC_ENFORCE_STRICT=1 PYTHONUTF8=1 python -m pytest` on test_presence_only_merge_aware.py + test_bp_100k_3.py + test_bp_1100b_5.py -> 26 passed. check_file_size passed (245 lines counted); ruff clean.
red_baseline_results:
  - test_name: test_merge_bringing_in_branch_added_presence_only_assertion_passes
    result: green

### 2026-10-17 09:35 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-17_c6fdda65
No high-confidence findings. Plain commit unchanged; merge/revert/cherry-pick judge only get_authored_change().diff_text; None on could-not-check is never widened; emit_result(OUTCOME_COULD_NOT_CHECK)+return 0 matches check_contract_shrinking; HOOK_TEST_DIFF short-circuits to the staged diff. Tests use real git, no mocks; test 1 would pass if the hook ignored merges, but test 2 (resolution-added assertion refused, with clean-merge control) fails in that case, so the pair is sound. Medium: [M-1] no revert/cherry-pick test; [M-2] could-not-check path untested. Low: docstring sentence in ARCHITECTURE reads "...unscoped diff and the `presence_only_assertion_guard` config section" (missing words); "covers: UNKNOWN" tags. 17 tests pass (new + test_bp_1100b_5).
