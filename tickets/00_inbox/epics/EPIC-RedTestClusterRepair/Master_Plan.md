---
title: "EPIC: Repair the residual red-test clusters blocking the blocking CI gate"
type: epic
status: todo
components:
  - testing_quality
  - build_pipeline
created: 2026-07-15
depends_on: []
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
---

# EPIC: Residual Red-Test Cluster Repair

## Goal

Turn the currently-RED pytest clusters GREEN on a fresh `origin/main` so the CI
`test` job can become a blocking gate (BP-1200b) and be added to branch
protection (BP-1200c). This epic covers **only the residual clusters that no
other epic or branch owns** — see the coverage map below. It deliberately does
**not** duplicate work already owned by the two 2026-07-14 build_pipeline audit
epics or the `fix/testsuite-green-clusters` salvage branch.

## Context

Ground truth from CI `test` job on `origin/main` (run `29403216629`, 2026-07-15):
`81 failed, 2930 passed, 10 skipped, 26 xfailed`. There are **zero collection
errors** — `install_shims` resolves every module on CI's Linux runner (the local
WSL `build.py` hang that produces spurious collection errors is not in scope).
The count is *rising* over time because the phantom-remediation work is removing
xfail masks, so previously-hidden genuine tests now run RED.

The failures cluster into root causes. This epic was scoped by a gap analysis
(2026-07-15) that mapped every cluster against the two audit epics and the
in-flight `fix/testsuite-green-clusters` branch.

## Coverage map (why these tickets and not others)

**Owned elsewhere — NOT in this epic:**

| Cluster / tests | Owner | Notes |
|---|---|---|
| Flip `.github/workflows/ci.yml` `test` job to blocking (BP-1200b) | `EPIC-BuildPipelinePhantomRemediation` ticket 05 | The gate-flip itself; depends on the suite being green first. |
| `test_build_tracked_source_guard` (BP-900c-3) | `EPIC-BuildPipelinePhantomRemediation` ticket 01 | `_suggest_action` branch-order code fix. |
| `test_verify_precommit_active` / deployed hook parity (BP-100i-3) | `EPIC-BuildPipelinePhantomRemediation` ticket 03 | Missing-deployed-script promoted INFO→blocking. |
| Cluster 1 (`test_build_package_version`, `test_build_guard_real_package`, `test_build_version_wiring`, `test_build_changelog_placeholder`) — `AttributeError: module 'build' has no attribute …` | **Candidate fix exists** in `fix/testsuite-green-clusters` commit `c990bb89` (the `unit_tests/build → build_guards` rename that removes the `import build` shadowing of `scripts/build.py`). | Pending salvage/rebase+merge of that branch. If it does NOT land, re-scope into this epic. |
| Cluster 2 (`test_check_ac_schema`, 14) | Candidate fix in `c990bb89` | Pending salvage. |
| Cluster 3 (`test_setup_ticket_worktree`, 10) | Candidate fix in `c990bb89` | Pending salvage. |
| Cluster 6 partial (`test_skill_registry`, `test_check_surface_components_e3`, `test_build_artifact_parity`) | Candidate fix in `c990bb89` | Pending salvage. |

> `fix/testsuite-green-clusters` (worktree `testfix-reassess`) is ~20 PRs stale
> (branched at #290) and is one un-reviewed ~1,500-line commit authored as
> `Test User`. It must be rebased onto current `origin/main` and reviewed before
> its fixes can be trusted/merged. Tracking that salvage is out of scope here;
> this epic assumes it lands and covers what it does NOT touch.

**Residual — owned by THIS epic** (no ticket or branch touches these):

| # | File | Cluster | Failing tests | Status |
|---|------|---------|---------------|--------|
| 01 | [01_workflow_parity_tests.md](./01_workflow_parity_tests.md) | 4 | `test_partial_run_recovery` (3), `test_final_gate_and_commit_message` (1), `test_commit_stage_output_behavioral` (1) | `[ ]` |
| 02 | [02_workflow_variant_transform.md](./02_workflow_variant_transform.md) | 5 | `test_workflow_variant_transform` (4) | `[ ]` |
| 03 | [03_component_and_hook_schema_drift.md](./03_component_and_hook_schema_drift.md) | 6 | `test_check_components_minimum_schema` (1), `test_transform_hooks_and_autofix_emission` (1), `test_build_phases` (2) | `[ ]` |
| 04 | [04_psutil_dev_dependency.md](./04_psutil_dev_dependency.md) | 6 | `test_sweep_processes` (1) | `[ ]` |
| 05 | [05_defect_fixes_misc.md](./05_defect_fixes_misc.md) | misc | `test_defect_fixes` (2) + verify `test_verify_precommit_active` ownership | `[ ]` |

## Parallel-safety

The five tickets touch disjoint test files and disjoint source/config areas
(workflow JS parity, workflow-variant build output, commit_guardian component
schema, `requirements-dev.txt`, misc). No `depends_on` edges — parallel-safe.

## Exit criteria

- Every residual test above passes on a fresh `origin/main` CI run.
- Combined with the salvage of `c990bb89` and the two audit epics, `pytest
  tests/ unit_tests/` is green and deterministic — unblocking BP-1200b/BP-1200c.
- Re-run the live CI diagnosis before closing: the count is a moving target.
