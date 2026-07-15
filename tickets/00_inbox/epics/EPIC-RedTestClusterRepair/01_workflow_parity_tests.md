---
title: "Fix workflow script↔template parity tests stale after the E2 engine port"
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

# 01: Fix workflow script↔template parity tests stale after the E2 engine port

## Actor / Goal

As a maintainer, I want the workflow script↔template parity tests to reflect the
E2 workflow-engine calling convention, so that this cluster stops failing and the
CI `test` job can become blocking.

## Context

Cluster 4 of the 2026-07-15 red-test gap analysis. On CI (`origin/main` run
`29403216629`) these fail:

- `unit_tests/test_partial_run_recovery.py` (3): e.g.
  `test_run_function_parity`, `test_scan_orphaned_ac_drafts_function_parity`,
  `test_resolve_orphaned_drafts_function_parity`.
- `unit_tests/test_final_gate_and_commit_message.py` (1):
  `test_scripts_and_templates_run_function_are_in_parity`.
- `unit_tests/test_commit_stage_output_behavioral.py` (1):
  `test_scripts_and_templates_are_in_parity`.

Root cause: the tests assert the deployed `scripts/workflows/*.js` are
byte/structurally identical to `templates/workflows-js/*.js` for a `run(...)`
signature of the form `async function run({ userInput, agent })`, but the E2
engine port changed the canonical form to a **top-level body** (`async function
run() — E2 executes the top-level body directly`). The assertions lock in the
pre-port signature. Example diff from CI:
`'async function run({ userInput, agent }' != 'async function run() — E2 executes the top-level body…'`.

This cluster is **not** owned by either build_pipeline audit epic and is **not**
touched by the `c990bb89` salvage commit on `fix/testsuite-green-clusters` (which
only touched `plan-feature.js` parity + `test_workflow_dual_engine`, not these
three tests). See the epic Master_Plan coverage map.

## Acceptance Criteria

```gherkin
Given a fresh origin/main checkout after build.py runs
When pytest runs the three parity test modules in this cluster
Then all parity assertions pass against the E2 top-level-body run() convention
  and no assertion references the obsolete `run({ userInput, agent })` signature
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_partial_run_recovery.py / test_final_gate_and_commit_message.py / test_commit_stage_output_behavioral.py | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Determine the intended parity contract post-E2-port: are scripts meant to
      be regenerated from templates by `build.py`, or do the tests need to accept
      the top-level-body form? (Check how the E2 engine deploys workflow JS.)
- [ ] Fix the three test modules to assert the current convention — OR fix the
      template/deploy step if the drift is a real regression, not a stale test.
      Decide per the "fix the test unless production regressed" rule.
- [ ] Run the three modules green on a fresh build; confirm no obsolete-signature
      assertions remain.

## Risk & Safety

- Touches money? No.
- Touches data? No — test/parity fixes only.
- Reversibility? Fully reversible.
