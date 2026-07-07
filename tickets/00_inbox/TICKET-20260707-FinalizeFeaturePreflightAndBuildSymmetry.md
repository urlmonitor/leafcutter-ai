---
title: "finalize-feature: resolve pre-flight target from input + build/deploy symmetry between baseline and post-merge test runs"
status: todo
components:
  - finalize
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

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
