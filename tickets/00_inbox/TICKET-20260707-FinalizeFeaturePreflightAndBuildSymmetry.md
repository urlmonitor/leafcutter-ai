---
title: "finalize-feature: resolve pre-flight target from input + build/deploy symmetry between baseline and post-merge test runs"
status: in_progress
components:
  - build_pipeline
created: 2026-07-07
origin_agent: BrainCandy
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows/finalize-feature.md
  - unit_tests/workflows/test_finalize_feature_preflight.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
ac_traceability:
  l2:
    - FIN-100g-1
    - FIN-100a-4
  ac_path: docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/
---

# finalize-feature: pre-flight target resolution + baseline/post-merge build symmetry

## Actor / Goal

As an operator running `/finalize-feature`, I want the workflow to (a) resolve the
target branch and worktree from explicit input rather than the ambient CWD, and
(b) run the Step 3 post-merge test suite with the same build/deploy setup as the
Step 0 baseline — so that finalize can be driven from anywhere without a spurious
"must be run from a feature branch" abort, and so that deploy-dependent tests are
never falsely triaged as regressions.

## Context

Both defects were surfaced during the GE-114-H2 finalize (PR #216) and required
manual workarounds to complete:

- **Gap A (FIN-100g-1):** the pre-flight dispatches `status-checker` with bare
  `git branch --show-current` / `git rev-parse --show-toplevel`, which resolve
  against the *ambient process CWD*. When finalize is invoked from the main repo
  (or any directory that is not the target worktree) the pre-flight resolves
  `branch: "main"` and aborts with "must be run from a feature branch", ignoring the
  branch the caller actually named. EPIC-FinalizeFeatureHardening ticket 06 threaded
  `git -C "${WORKTREE_ROOT}"` into all **downstream** steps but deliberately left the
  pre-flight untouched (WORKTREE_ROOT does not exist until the pre-flight computes it).
- **Gap B (FIN-100a-4):** Step 0 (baseline on origin/main) runs `scripts/build.py`
  (install_shims deploys `scripts/commit_guardian/`, `scripts/feedback/`, etc. and the
  `.pre-commit-config.yaml`) before pytest, but Step 3 (post-merge) does **not**. The
  asymmetry makes ~13 deploy-dependent tests fail RED in Step 3 while passing in the
  Step 0 baseline, and the triage set-difference (`post_merge − baseline`) then
  misclassifies them as regressions → false `test_regression` halt.

The primary edit target is `templates/workflows-js/finalize-feature.js` (both the
pre-flight agent dispatch and the Step 3 test-runner dispatch), with the step-map doc
updated to match. Both changes touch the same file, so they are delivered as one ticket
to avoid a self-conflict.

## Acceptance Criteria

<!-- FIN-100g-1 — pre-flight resolves target from input, not ambient CWD -->
```gherkin
# covers: FIN-100g-1
Given the finalize workflow receives a target feature branch as input (args)
And the process CWD is a different repository or worktree (for example the main repo checked out on main)
When the pre-flight resolves branch and worktree_root
Then it locates the worktree in which the target branch is checked out (for example via `git worktree list --porcelain`) and anchors subsequent git reads on that path with `git -C <path>`
And it returns branch equal to the target feature branch (not the CWD's branch)
And it returns worktree_root equal to that worktree's absolute path
And the "must be run from a feature branch" abort fires only when the resolved TARGET branch is main/master — never merely because the ambient CWD is on main
And when no explicit target is provided the pre-flight falls back to CWD-based detection unchanged (backward compatible)
And if the target branch has no checked-out worktree the workflow returns a clear error naming the branch, rather than silently resolving to the wrong repo
```

<!-- FIN-100a-4 — baseline (Step 0) and post-merge (Step 3) use identical build/deploy setup -->
```gherkin
# covers: FIN-100a-4
Given Step 0 captures the baseline by running scripts/build.py (install_shims deploys scripts/commit_guardian, scripts/feedback, scripts/doc_compliance and the .pre-commit-config.yaml) before executing the full test suite in the temporary origin/main worktree
When Step 3 runs the full test suite on the post-merge feature worktree
Then Step 3 first performs the same build/deploy step against the feature worktree root before invoking the suite
And both runs collect and deploy the identical set of runtime artifacts
So that deploy-dependent tests cannot fail RED in one run and pass in the other purely because of missing build state
And the regression_candidates set difference (post_merge_failures minus baseline_failures) reflects only real code differences, never environment skew
```

## Test Requirements

Create `unit_tests/workflows/test_finalize_feature_preflight.py` covering:

- **FIN-100g-1:** invoking the pre-flight logic with a target branch while the CWD is
  on `main` resolves `branch`/`worktree_root` to the *target* worktree, not `"main"`;
  the main/master abort keys off the resolved target; the no-worktree case returns a
  clear branch-named error; and the no-target case still falls back to CWD detection.
- **FIN-100a-4:** a guard asserting that BOTH the Step 0 baseline dispatch prompt and
  the Step 3 test-runner dispatch prompt in `finalize-feature.js` contain the
  `build.py` / install_shims instruction (so the two runs cannot drift apart).

All new tests must be RED before implementation and GREEN after.

## Out of Scope

- Any change to the triage set-difference logic (FIN-100c) or the null-baseline
  conservative path (FIN-100c-3).
- Merging EPIC-FinalizeFeatureHardening (the downstream `git -C` threading from ticket
  06 is already live on main; this ticket only fixes the pre-flight + Step 3 build).

## Sign-offs

- [x] test-writer — 2026-07-08 09:15
- [x] python-coder — 2026-07-08 10:45
- [x] test-runner — 2026-07-08 11:30
- [x] pr-reviewer — 2026-07-08 12:00
- [ ] commit
- [ ] pull-request

## Comments

### 2026-07-08 09:15 — test-writer (status: ok)
feedback-id: fb_2026-07-08_b5bffd6e
completion_manifest:
  test_file_created: true
  all_tests_red: true
  fin_100g1_coverage: true
  fin_100a4_coverage: true
  workflows_dir_scaffolded: true
Created `unit_tests/workflows/test_finalize_feature_preflight.py` with 9 failing tests covering FIN-100g-1 (5 tests: pre-flight reads `args.target_branch`, uses `git worktree list --porcelain`, handles no-worktree error, falls back to CWD, abort anchored to resolved target) and FIN-100a-4 (4 tests: Step 0 and Step 3 both contain build.py, symmetry guard, ordering guard). All 9 tests confirmed RED (exit code 1) against the current `finalize-feature.js`. Also scaffolded `unit_tests/workflows/__init__.py` and `unit_tests/workflows/conftest.py`.

### 2026-07-08 10:45 — python-coder (status: ok)
feedback-id: fb_2026-07-08_6c48f954
completion_manifest:
  fin_100g1_preflight_target_resolution: true
  fin_100a4_step0_build_py: true
  fin_100a4_step3_build_py: true
  fin_100a4_ordering_guard: true
  step_map_doc_created: true
  all_9_tests_green: true
Updated `templates/workflows-js/finalize-feature.js` with two fixes: (1) FIN-100g-1 — pre-flight now reads `args.target_branch`; when provided, uses `git worktree list --porcelain` to locate the correct worktree, returns a clear "no worktree for branch" error when the branch is not checked out, and falls back to CWD-based `git branch --show-current` detection when no target is given; the main/master abort fires on the resolved target, not the ambient CWD; (2) FIN-100a-4 — Step 0 (Step C) and Step 3 both now include a `scripts/build.py --target-dir` instruction before the test suite, with build.py ordered before pytest in Step 3's prompt text. Created `templates/workflows/finalize-feature.md` as the step-map documentation file. All 9 tests confirmed GREEN.

### 2026-07-08 11:30 — test-runner (status: ok)
feedback-id: fb_2026-07-08_39471c47
completion_manifest:
  all_9_tests_green: true
  no_regressions_in_workflows_suite: true
All 9 tests in `unit_tests/workflows/test_finalize_feature_preflight.py` passed GREEN: 5 FIN-100g-1 tests (pre-flight reads args.target_branch, uses git worktree list --porcelain, handles no-worktree error, falls back to CWD, abort anchored to resolved target) and 4 FIN-100a-4 tests (Step 0 and Step 3 both contain build.py, symmetry guard, ordering guard). The broader `unit_tests/workflows/` suite also ran clean with no regressions (9/9 passed, this is the only file in the directory).

### 2026-07-08 12:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-07-08_4c0aaef7
completion_manifest:
  fin_100g1_targetbranch_read_from_args: true
  fin_100g1_worktree_list_porcelain_in_prompt: true
  fin_100g1_no_worktree_error_returned: true
  fin_100g1_cwd_fallback_present: true
  fin_100g1_abort_fires_on_resolved_target: true
  fin_100a4_step0_build_py_before_pytest: true
  fin_100a4_step3_build_py_before_pytest: true
  finalize_feature_md_doc_updated: true
  no_unintended_regressions: true
Both ACs verified in the staged diff. FIN-100g-1: `const targetBranch = args.target_branch || null` is set before the pre-flight agent call; the prompt branches on targetBranch — when provided it instructs `git worktree list --porcelain` to locate the correct worktree, returns a clear branch-named error when no match is found, and falls back to `git branch --show-current` (CWD-based) when absent; the main/master abort fires on the RESOLVED BRANCH, not the ambient CWD. FIN-100a-4: Step 0 Step C and Step 3 both include `python3 scripts/build.py --target-dir` before their respective `pytest` invocations — build precedes test in both blocks as required. `templates/workflows/finalize-feature.md` documents both changes. Minor observation: `unit_tests/workflows/__init__.py` and `conftest.py` are not listed in `files_touched` but were noted in the test-writer sign-off as scaffold files — not a blocker.
