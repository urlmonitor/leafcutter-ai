---
title: "Fix pre-existing pytest baseline failures on main (non-required Test suite job)"
status: todo
components:
  - build_pipeline
  - worktree_manager
  - testing_quality
created: 2026-07-10
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
---

# Fix pre-existing pytest baseline failures on main

## Actor / Goal

In order to trust the `Test suite (pytest)` CI signal (currently chronically red on
main, which is why it is non-required and why `/finalize-feature` keeps false-flagging
regressions), we need the pre-existing failures fixed so a green pytest run means
something again.

## Context

The `Test suite (pytest)` job is red on `main` and has been for a while (non-required
gate; PRs merge on ruff + schema-diff only). Because it is chronically red,
`finalize-feature.js` can't distinguish real regressions from the baseline and repeatedly
halts on false `test_regression`. Diagnosed 2026-07-10 while finalizing
EPIC-PromptAssemblyHardening; the failing tests split into three distinct causes:

### Cluster 1 — `tests/test_build_phases.py` (deploy size mismatch — likely a real bug)
- `TestBuildWorkflowScriptsIncludesPlanFeature::test_build_workflow_scripts_includes_plan_feature`
- `TestPlanFeatureDeployedInConsumerConfig::test_plan_feature_deployed_in_consumer_config`

`build_workflow_scripts()` deploys `plan-feature.js` at **61,383 bytes** while the source
`templates/workflows-js/plan-feature.js` is **82,834 bytes**. The test asserts deployed
size == source size and fails (`61383 != 82834 : Content may have been silently
truncated`). Investigate the source-of-truth: is the deploy copying from a stale
committed `scripts/workflows/plan-feature.js`, from `templates/workflows/plan-feature.md`,
or truncating? This is the same deploy-path/source-of-truth family as the
`finalize-feature.md` collision (PR #251).

### Cluster 2 — `tests/test_setup_ticket_worktree.py` (test-mock bug)
- `TestBootstrapPoetryRepo::test_bootstrap_uses_poetry_when_pyproject_toml_present`
- `TestBootstrapPipRepo::test_bootstrap_uses_pip_when_requirements_dev_txt_present`
- `TestBootstrapNoManifestRepo::test_bootstrap_skips_dep_install_when_no_manifest`
- `TestBootstrapInstallFailureNonFatal::test_bootstrap_install_failure_is_non_fatal`

All four fail with `TypeError: the JSON object must be str, bytes or bytearray, not
MagicMock`. `setup_ticket_worktree.py` now `json.loads()` some subprocess output, but the
tests' mocks return a bare `MagicMock` instead of a JSON string. Fix the mocks to return
valid JSON (or the production code to tolerate the mocked shape) so the bootstrap paths
are actually exercised.

### Cluster 3 — deploy-dependent tests (CI-env, not logic)
`tests/commit_guardian/test_check_ac_done_on_merge.py` and several
`unit_tests/commit_guardian/test_check_ac_schema.py` cases invoke DEPLOYED
`scripts/commit_guardian/…` scripts. They pass in a built worktree (`build.py` run) but
fail in contexts where `build.py` has not run (finalize step 3; some CI paths). Decide the
fix: ensure the pytest CI job runs `build.py`/`install_shims` before pytest (it partially
does — verify), or make these tests build-independent (resolve the script from
`templates/…` when the deployed copy is absent). This cluster is also the root of the
`finalize-feature` step-3 false-regression (tracked separately).

## Acceptance Criteria

- [ ] AC-1: `tests/test_build_phases.py` plan-feature deploy tests pass — deployed `plan-feature.js` matches the canonical source (root-cause of the size mismatch fixed, not the assertion loosened).
- [ ] AC-2: `tests/test_setup_ticket_worktree.py` bootstrap tests pass — mocks provide valid JSON (or production tolerates the shape); the poetry/pip/no-manifest/install-failure paths are genuinely exercised.
- [ ] AC-3: The deploy-dependent AC-schema / check_ac_done_on_merge tests pass in the CI pytest job (either the job builds first, or the tests resolve scripts build-independently).
- [ ] AC-4: `python -m pytest tests/ unit_tests/` is green on main (0 failures), so the job can be promoted toward required and finalize's regression triage becomes trustworthy.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | tests/test_build_phases.py (plan-feature) | | |
| AC-2 | tests/test_setup_ticket_worktree.py | | |
| AC-3 | tests/commit_guardian/test_check_ac_done_on_merge.py; unit_tests/commit_guardian/test_check_ac_schema.py | | |
| AC-4 | full suite | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Cluster 1: trace `build_workflow_scripts()` source-of-truth for `plan-feature.js`; fix the deploy so deployed == `templates/workflows-js/plan-feature.js`; remove any stale committed deployed copy.
- [ ] Cluster 2: fix the `json.loads`/MagicMock mock setup in `test_setup_ticket_worktree.py`.
- [ ] Cluster 3: make the pytest CI job build before running (or make the deploy-dependent tests build-independent).
- [ ] Confirm full `pytest tests/ unit_tests/` green; consider promoting the job to required.

## Risk & Safety

- Touches money? No.
- Touches data? No — test + build-deploy fixes.
- Reversibility? Fully reversible via git.
