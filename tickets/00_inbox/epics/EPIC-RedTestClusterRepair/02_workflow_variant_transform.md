---
title: "Fix test_workflow_variant_transform: deployed workflows/stub.js fixture missing"
status: todo
components:
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
agents:
  test-writer: not_needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02: Fix test_workflow_variant_transform (missing deployed workflows/stub.js)

## Actor / Goal

As a maintainer, I want `test_workflow_variant_transform` to locate the workflow
build output it asserts on, so that this cluster stops failing.

## Context

Cluster 5 of the 2026-07-15 red-test gap analysis. On CI (`origin/main` run
`29403216629`) `unit_tests/test_workflow_variant_transform.py` fails 4 tests in
`TestBuildWorkflowScriptsEngineFromConfig` / `TestReachability`:

- `test_e2_engine_emits_byte_identical_file` — `AssertionError: Deployed file must exist`
- `test_sha256_idempotency_skips_unchanged_file` — `FileNotFoundError: …/output/workflows/stub.js`
- `test_auto_engine_defaults_to_identity` — `FileNotFoundError: …/output/workflows/stub.js`
- `test_synthetic_e2_workflow_is_readable_after_deploy` — `AssertionError: Deployed synthetic workflow must exist`

Root cause: the test builds workflow scripts from config and expects a deployed
`workflows/stub.js` in the output root, but the build-workflow-scripts phase does
not produce it under the test's setup (fixture/build-output mismatch — the
synthetic workflow is not written to the path the test reads). Either the test's
fixture setup no longer matches how `build_phases` deploys workflow JS, or the
deploy step regressed for the synthetic/stub case.

Not owned by either audit epic; not touched by `c990bb89`. See Master_Plan map.

## Acceptance Criteria

```gherkin
Given a fresh origin/main checkout
When test_workflow_variant_transform builds workflow scripts from its config
Then the deployed workflows/stub.js exists at the path the test reads
  and all four TestBuildWorkflowScriptsEngineFromConfig / TestReachability tests pass
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | unit_tests/test_workflow_variant_transform.py | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Reproduce the FileNotFoundError and trace where the test expects
      `output/workflows/stub.js` vs where the build-workflow-scripts phase writes.
- [ ] Fix the test fixture setup to deploy the synthetic workflow to the correct
      output path — OR fix the deploy phase if it regressed for the stub case.
- [ ] Run the four failing tests green on a fresh build.

## Risk & Safety

- Touches money? No.
- Touches data? No — test/build-output fixture only.
- Reversibility? Fully reversible.
