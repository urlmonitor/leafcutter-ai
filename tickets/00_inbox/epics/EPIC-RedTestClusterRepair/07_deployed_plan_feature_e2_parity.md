---
title: "Regenerate deployed plan-feature.js from E2 source (parity + build_phases)"
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
files_touched:
  - scripts/workflows/plan-feature.js
  - unit_tests/test_partial_run_recovery.py
  - unit_tests/test_final_gate_and_commit_message.py
  - unit_tests/test_commit_stage_output_behavioral.py
  - tests/test_build_phases.py
agents:
  test-writer: not_needed
  python-coder: failed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 07: Regenerate deployed plan-feature.js from the E2 source

## Actor / Goal

As a maintainer, I want the DEPLOYED `scripts/workflows/plan-feature.js` to match the E2
source template, so the workflow parity tests and `test_build_phases` go green **without**
regressing `/plan-feature`.

## Context

The salvage PR #300 originally "fixed" the plan-feature parity failures the WRONG way —
by reverting the **source** template to the stale E1 form (which would silently break
`/plan-feature` under the E2-only engine). That regression was removed from #300 (commit
`a9819e15`), leaving the correct-but-unfinished state: **source template is E2, deployed
`scripts/workflows/plan-feature.js` is stale E1**, so these parity tests fail:

- `unit_tests/test_partial_run_recovery.py` (3) — `test_run_function_parity`,
  `test_scan_orphaned_ac_drafts_function_parity`, `test_resolve_orphaned_drafts_function_parity`
- `unit_tests/test_final_gate_and_commit_message.py` (1) — `test_scripts_and_templates_run_function_are_in_parity`
- `unit_tests/test_commit_stage_output_behavioral.py` (1) — `test_scripts_and_templates_are_in_parity`
- `tests/test_build_phases.py` (2) — deployed sha mismatch / "Content may have been silently truncated"

Build direction (confirmed): `scripts/build_phases.py:683-685` copies FROM
`templates/workflows-js/` (source, authoritative) TO `scripts/workflows/` (deployed). The
deployed copy was never rebuilt after the E2 source port. **Correct fix: regenerate the
deployed output from the E2 source** — never revert the source to match stale output.

## Acceptance Criteria

```gherkin
Given the E2 source template templates/workflows-js/plan-feature.js on origin/main
When the deployed scripts/workflows/plan-feature.js is regenerated from it
Then the two files are in parity per the parity tests
  and test_partial_run_recovery, test_final_gate_and_commit_message,
  test_commit_stage_output_behavioral, and test_build_phases all pass (addopts="" and
  AC_ENFORCE_STRICT=1)

Given the regenerated deployed file
Then it is the E2 top-level-body form (NOT E1 run({userInput,agent})) so /plan-feature
  still dispatches agents under the E2 engine — verify by confirming top-level await
  agent() calls remain and test_dispatch_order_plan_feature is NOT xfail-masked

Given parity
Then parity is achieved by fixing the deployed output, NOT by editing the source template
  or weakening/deleting the parity assertions
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_partial_run_recovery / test_final_gate / test_commit_stage | scripts/workflows/plan-feature.js | |
| AC-2 | test_build_phases.py | scripts/workflows/plan-feature.js | |

## Test Requirements

```yaml
tests:
  - name: test_run_function_parity
    file: unit_tests/test_partial_run_recovery.py
    covers: [build_pipeline]
    asserts: deployed scripts/workflows/plan-feature.js run() body is in parity with the E2 source template.
  - name: test_scan_orphaned_ac_drafts_function_parity
    file: unit_tests/test_partial_run_recovery.py
    covers: [build_pipeline]
    asserts: scanOrphanedAcDrafts parity between deployed and source.
  - name: test_resolve_orphaned_drafts_function_parity
    file: unit_tests/test_partial_run_recovery.py
    covers: [build_pipeline]
    asserts: resolveOrphanedDrafts parity between deployed and source.
  - name: test_scripts_and_templates_run_function_are_in_parity
    file: unit_tests/test_final_gate_and_commit_message.py
    covers: [build_pipeline]
    asserts: deployed vs template run() are in parity (E2 top-level-body form).
  - name: test_scripts_and_templates_are_in_parity
    file: unit_tests/test_commit_stage_output_behavioral.py
    covers: [build_pipeline]
    asserts: deployed vs template commit-stage-output are in parity.
  - name: test_plan_feature_deployed_in_consumer_config
    file: tests/test_build_phases.py
    covers: [build_pipeline]
    asserts: the deployed plan-feature.js matches source sha (no silent truncation) after build.
```

## Sign-offs

- [ ] python-coder — failed 2026-07-15 14:30

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-07-15 14:30 — python-coder (status: blocker)

feedback-id: fb_2026-07-15_31386297
completion_manifest:
  build_direction_confirmed: true
  e2_identity_transform_confirmed: true
  parity_tests_require_byte_identical:
    result: false
    reason: "test_build_phases.py::test_build_workflow_scripts_includes_plan_feature and test_plan_feature_deployed_in_consumer_config use SHA-256 and file-size comparisons between the build output (from templates/workflows-js/plan-feature.js) and scripts/workflows/plan-feature.js — byte-identical equality is the only way to pass these tests."
    remediation: "test-writer must update the 24 behavioral tests in test_partial_run_recovery.py, test_final_gate_and_commit_message.py, and test_commit_stage_output_behavioral.py to use E2 calling conventions (global agent, no run() wrapper, mock phase/args/agent/log in vm context) before python-coder can regenerate the deployed file."
  behavioral_tests_remain_green:
    result: false
    reason: "Copying the E2 template to scripts/workflows/plan-feature.js breaks 24 currently-passing behavioral tests. The E2 template uses agent as a global (not a function parameter), has no run() wrapper, and executes phase('Stage 0') at top-level — but the behavioral tests use E1 calling conventions: scanOrphanedAcDrafts(mockAgent, acStoreDir), run({ userInput, agent: mockAgent }), and commitStageOutput(mockAgent, ...). When the E2 source is loaded in vm.Script, the top-level phase('Stage 0') throws ReferenceError immediately (phase is not a Node.js global), or wrong function signatures cause incorrect results."
    remediation: "Respawn test-writer to update behavioral tests in the three unit_tests/ files to use E2 calling conventions, then respawn python-coder to copy the template to deployed."

Attempted: Analyzed the build direction (build_phases.py:683-685 identity-transforms E2 source to deployed), confirmed test_dispatch_order_plan_feature passes (tests the template E2 form via run_workflow_under_e2 harness), and verified that copying templates/workflows-js/plan-feature.js to scripts/workflows/plan-feature.js makes all 7 parity/build_phases tests green.

Blocked because: Making deployed = E2 template causes a net regression from 7 failing / 40 passing to 31 failing / 16 passing — 24 previously-green behavioral tests (test_partial_run_recovery.py, test_final_gate_and_commit_message.py, test_commit_stage_output_behavioral.py) go red. These tests use E1-form calling conventions (agent as function parameter, run() wrapper) that are incompatible with the E2 template's global-agent pattern and top-level body execution. The system prompt forbids breaking currently-passing tests and forbids modifying test files.

Remediation: test-writer must update the behavioral tests in the three unit_tests/ files to use E2 calling conventions. Specifically: (1) add phase, args, agent, and log as mock no-op globals in vm.createContext; (2) remove agent parameter from scanOrphanedAcDrafts/resolveOrphanedDrafts/commitStageOutput calls; (3) replace run({ userInput, agent: mockAgent }) invocations with the run_workflow_under_e2() harness pattern from test_workflow_dual_engine.py. Once those tests are updated, respawn python-coder to copy the template (identity transform) to scripts/workflows/plan-feature.js.

## Implementation Tasks

- [ ] Determine how the deployed file is produced (build_phases workflow deploy —
      byte copy vs transform) and regenerate `scripts/workflows/plan-feature.js` from the
      current E2 source (run the workflow-deploy phase, or reproduce its exact transform;
      do NOT hand-diverge).
- [ ] Confirm the deployed file is the E2 top-level-body form.
- [ ] Run the 5 parity/build_phases tests green with `-o addopts=""` and `AC_ENFORCE_STRICT=1`.
- [ ] Confirm `test_dispatch_order_plan_feature` (guard) is genuinely green, not xfail'd.

## Risk & Safety
- Touches money? No.
- Touches data? No — regenerates a deployed workflow script from its source.
- Reversibility? Fully reversible.
