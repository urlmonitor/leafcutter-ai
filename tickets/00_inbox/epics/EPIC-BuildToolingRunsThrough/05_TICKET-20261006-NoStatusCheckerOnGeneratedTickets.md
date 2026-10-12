---
title: "Generated build tickets no longer get status-checker from the guardrail matrix"
status: todo
components:
  - ticket_creation_pipeline
  - ac_driven_dev
created: 2026-10-06
depends_on: []
priority: medium
complexity: low
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target:
  - config
risk_surface: contract_boundary
files_touched:
  - config/guardrail_gates.yaml
  - unit_tests/test_guardrail_matrix_status_checker.py  # new
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: not_needed
  status-checker: not_needed
---

# 05: Generated build tickets no longer get status-checker from the guardrail matrix

## Actor / Goal

As the ticket generator, I want the guardrail matrix to stop listing status-checker,
so that a generated build ticket gets `status-checker: needed` only when its AC is a
diagnosis AC. Then build runs no longer start with a priority-1 status-checker that
hands off and loops. The cells that listed it get architect-review instead (user
decision F5, 2026-10-06).

## Context

Part of EPIC-BuildToolingRunsThrough (design section 4).

**Root cause**
- status-checker is not in the generator's canonical order (`scripts/ac_store/_gtfa_constants.py:180-195`). It enters only through the guardrail config. `_union_guardrail_agents` (`scripts/ac_store/_gtfa_agents_inputs.py:220-267`, with updates at 247 and 265) merges that config into the needed set.
- `config/guardrail_gates.yaml` lists it at:
  - line 177 (`model` / `contract_boundary`);
  - line 190 (`model` / `cost`);
  - line 197 (`config` / `contract_boundary`);
  - lines 322-328 (the flow-change gate for `config` / `contract_boundary`).
- DK-400a-1 is `[code, config]` with `contract_boundary`, so it hits two of these.
- The generator places status-checker just before commit (`scripts/ac_store/_gtfa_agents_map.py:156-172`). But the driver sorts by `phaseOrder`, where it is priority 1 (`templates/workflows-js/build-feature.js:409`; `build-ticket.js:271`).
- The registry says `default_status: not_needed`, with diagnosis-only triggers (`config/agent_registry.json:1296-1325`). No ADR (ADR-017 does not name it) and no AC mandates it in the matrix.

**Rule and fix**
- A generated build ticket has status-checker `not_needed` unless the AC's `assigned_agent` is status-checker (diagnosis ACs).
- Following F5, replace status-checker with architect-review in every cell that listed it:
  - `model` / `contract_boundary` and `model` / `cost` already list architect-review, so status-checker is simply removed (no duplicate);
  - `config` / `contract_boundary` becomes `[architect-review, pr-reviewer]`;
  - the flow-change gate for `config` / `contract_boundary` gets `mandatory_agents: [architect-review, pr-reviewer]`, and its `phase_constraint` text names architect-review.
- Tickets already generated are not migrated (the DK tickets were fixed by hand).

**AC traceability.** No AC in the store covers the matrix's status-checker cells. F5
is the authority. The tests carry `covers: ACD-400b-1`, the generator's agents-map
contract and the nearest existing AC. If the business-analyst adds a dedicated AC,
retag the tests.

## Constraints

- **Test-file ratchet.** `unit_tests/test_generate_ticket_from_ac.py` measures 2393 / 400, so the ratchet refuses any growth. The design's tests therefore go in a new file, `unit_tests/test_guardrail_matrix_status_checker.py`.
- **Build mirrors.** `.leafcutter/config/guardrail_gates.yaml` is a build output. Run `python scripts/build.py` after the config edit and stage every tracked output it changes.
- The existing fixture-YAML tests (`unit_tests/test_generate_ticket_from_ac.py:933-990`, `unit_tests/test_bo_2200a_3.py:82`) use their own YAML and stay green unchanged.

## Acceptance Criteria

- [ ] AC-1: `config/guardrail_gates.yaml` lists status-checker in no matrix cell and no flow-change gate.
  - `model` / `contract_boundary` and `model` / `cost` list architect-review once.
  - `config` / `contract_boundary` is `[architect-review, pr-reviewer]`.
  - The `config` / `contract_boundary` flow-change gate's `mandatory_agents` are `[architect-review, pr-reviewer]`, and its `phase_constraint` names architect-review.
- [ ] AC-2: Walking every (change_target, risk_surface) cell of the **real** `config/guardrail_gates.yaml` through `_build_agents_map`, with `assigned_agent: python-coder`, never yields `status-checker: needed`.
- [ ] AC-3: An AC whose `assigned_agent` is status-checker still yields `status-checker: needed`.
- [ ] AC-4: A generated ticket for `config` / `contract_boundary` has `architect-review: needed`.
- [ ] AC-5: The existing fixture-YAML generator tests stay green unchanged.

## Test Requirements

```yaml
tests:
  - name: test_no_real_guardrail_cell_makes_status_checker_needed
    file: unit_tests/test_guardrail_matrix_status_checker.py
    covers:
      - ACD-400b-1
    asserts: >-
      Loading the real config/guardrail_gates.yaml, every (change_target,
      risk_surface) cell and every flow-change gate is passed through
      _build_agents_map with assigned_agent python-coder. No resulting agents
      map has status-checker set to needed. The cell list comes from the YAML
      itself, not from a list in the test.
    framework: pytest
    type: unit
    angle: real_artifact
  - name: test_assigned_status_checker_is_still_needed
    file: unit_tests/test_guardrail_matrix_status_checker.py
    covers:
      - ACD-400b-1
    asserts: >-
      With the real guardrail YAML, an AC whose assigned_agent is status-checker
      gets status-checker needed from _build_agents_map, for a
      config/contract_boundary and a code/internal pair.
    framework: pytest
    type: unit
    angle: boundary
  - name: test_config_contract_boundary_gets_architect_review
    file: unit_tests/test_guardrail_matrix_status_checker.py
    covers:
      - ACD-400b-1
    asserts: >-
      With the real guardrail YAML, change_target config with risk_surface
      contract_boundary yields architect-review needed and pr-reviewer needed,
      and status-checker is absent or not_needed.
    framework: pytest
    type: unit
    angle: criterion
  - name: test_flow_change_gate_names_architect_review_not_status_checker
    file: unit_tests/test_guardrail_matrix_status_checker.py
    covers:
      - ACD-400b-1
    asserts: >-
      In the real YAML, the flow-change gate entry for config/contract_boundary
      has mandatory_agents [architect-review, pr-reviewer], and its
      phase_constraint text does not mention status-checker.
    framework: pytest
    type: unit
    angle: real_artifact
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_flow_change_gate_names_architect_review_not_status_checker, test_no_real_guardrail_cell_makes_status_checker_needed | | |
| AC-2 | test_no_real_guardrail_cell_makes_status_checker_needed | | |
| AC-3 | test_assigned_status_checker_is_still_needed | | |
| AC-4 | test_config_contract_boundary_gets_architect_review | | |
| AC-5 | existing test_generate_ticket_from_ac.py and test_bo_2200a_3.py runs | | |

## Implementation Tasks

### test-writer
- [x] Write `unit_tests/test_guardrail_matrix_status_checker.py`, loading the real `config/guardrail_gates.yaml`, with the four tests above.

### python-coder
- [x] Edit `config/guardrail_gates.yaml`: lines 177, 190 and 197, and the flow-change gate at 322-328 (mandatory_agents and phase_constraint text).
- [x] Run `python scripts/build.py` and stage the tracked outputs.

### test-runner / pr-reviewer / commit
- [x] Run `unit_tests/test_generate_ticket_from_ac.py`, `unit_tests/test_bo_2200*` and the new file. pr-reviewer confirms that no other config or doc lists the removed cells.

## Risk & Safety

- Touches money? No.
- Touches data? No. Config only; tickets already generated are not rewritten.
- `config` / `contract_boundary` tickets now get an architect-review pass before coding, where before they got a status-checker. That is slightly more review cost, by design (F5).
- Reversibility: revert the YAML.

## Out of Scope

- Migrating tickets that were already generated.
- Ticket 02's handoff pair cap, which already stops any remaining status-checker loop.

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-10-06 15:36 — test-writer (status: ok)
feedback-id: (submit-failed)
Wrote unit_tests/test_guardrail_matrix_status_checker.py (4 tests, pytest) against the real config/guardrail_gates.yaml and the real _build_agents_map. Cells are read from the YAML itself (matrix rows plus flow_change_gates). With AC_ENFORCE_STRICT=1: 3 failed, 1 passed. Without it, the two ACD-400b-1 tests xfail through the AC-enforcement mask, as the AC is not yet done.
cross_layer_seam_answer: covered (producing side: config/guardrail_gates.yaml; consuming side: _build_agents_map via _union_guardrail_agents)
red_baseline:
  - test_name: test_no_real_guardrail_cell_makes_status_checker_needed
    file: unit_tests/test_guardrail_matrix_status_checker.py
    error: "AssertionError: cells still making status-checker needed: [('config', 'contract_boundary'), ('model', 'contract_boundary'), ('model', 'cost')]"
  - test_name: test_assigned_status_checker_is_still_needed
    file: unit_tests/test_guardrail_matrix_status_checker.py
    error: "green_at_baseline (guard): passes today; an assigned status-checker is already needed"
  - test_name: test_config_contract_boundary_gets_architect_review
    file: unit_tests/test_guardrail_matrix_status_checker.py
    error: "AssertionError: architect-review is 'not_needed' (assert 'not_needed' == 'needed')"
  - test_name: test_flow_change_gate_names_architect_review_not_status_checker
    file: unit_tests/test_guardrail_matrix_status_checker.py
    error: "AssertionError: mandatory_agents ['status-checker', 'pr-reviewer'] != ['architect-review', 'pr-reviewer']"

### 2026-10-06 15:45 — python-coder (status: ok)
feedback-id: (submit-failed)
Edited config/guardrail_gates.yaml only: removed status-checker from model/contract_boundary and model/cost (architect-review already listed, no duplicate); config/contract_boundary is now [architect-review, pr-reviewer]; the config/contract_boundary flow_change_gates entry has mandatory_agents [architect-review, pr-reviewer] and its phase_constraint now names architect-review. No code change needed. No tracked build mirror exists (.leafcutter/config is untracked build output), so build.py was not run.
Strict tests: unit_tests/test_guardrail_matrix_status_checker.py 4 passed. All 28 unit_tests files mentioning guardrail_gates: 251 passed, 1 failed (unit_tests/ac_store/test_tkt_500f_6_iii_a.py::TestSinglePredicateOwner, fails identically with the old YAML, unrelated).
red_baseline_results:
  - test_no_real_guardrail_cell_makes_status_checker_needed: green
  - test_assigned_status_checker_is_still_needed: green
  - test_config_contract_boundary_gets_architect_review: green
  - test_flow_change_gate_names_architect_review_not_status_checker: green

### 2026-10-06 15:50 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Reviewed the staged diff (config/guardrail_gates.yaml, unit_tests/test_guardrail_matrix_status_checker.py, this ticket). No high-confidence and no medium findings.
- YAML: status-checker appears nowhere in the file. model/contract_boundary and model/cost list architect-review once. config/contract_boundary is [architect-review, pr-reviewer]. The flow-change gate has mandatory_agents [architect-review, pr-reviewer] and its phase_constraint names architect-review, which is accurate.
- Tests: they load the real YAML and call the real _build_agents_map. The cell list is derived from the YAML itself, not hard-coded. The boundary and criterion tests are not tautological.
- Other readers: templates/agents/ticket-supervisor.md and building-epics SKILL.md only reference the file path. No doc under docs/reference, docs/how-to or docs/explanation lists the matrix cells. The fixture-YAML tests (test_bo_2200a_3.py:82, test_generate_ticket_from_ac.py:951) use their own YAML and are unaffected.
- Suppressed: low-confidence nits only.

### 2026-10-06 16:10 — test-runner (status: ok)
feedback-id: (submit-failed)
All runs with AC_ENFORCE_STRICT=1. No failure is attributable to this ticket: every failure outside the pre-existing known one also fails in the base-commit worktree build-tooling-done-proof (no YAML change) or is a load-sensitive perf-timing test.
- Cmd 1 (new file): 4 passed, 0 failed.
- Cmd 2 (non-ac_store files reading guardrail_gates / calling generate_ticket_from_ac / _build_agents_map, -n auto): 334 passed, 3 failed. All 3 pre-existing (fail identically at base): test_acd_1200a_14_i::test_git_rev_parse_failure_falls_back_with_warning, test_acd_1200b_4::test_no_tty_no_flag_fails_clearly, test_bo_2600a_5::test_implemented_by_written_repo_relative (backslash path, Windows).
- Cmd 3 (unit_tests/ac_store + tests/ac_store, -n auto): 880 passed, 14 failed, 4 skipped, 6 xfailed. Known pre-existing: test_tkt_500f_6_iii_a. 10 more fail identically at base (test_bo_2900d_1_eligibility_exemption, test_pytest_ac_enforcement x3, test_done_proof_composite_js x3, test_tkt_500f_5_i_registry_fallback, test_pytest_ac_enforcement_strict_on_ci x2; subprocess probes hit Windows temp-dir collection errors). 3 perf-timing tests (test_dependency_wiring ac1_performance, test_tree_traversal ac1_performance, test_readiness_gate ac1_performance) failed only under -n auto load and passed or flip between base and branch on serial rerun (different one failed in each worktree), so flaky, not caused by this change.
completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: "Failures remain, none caused by this ticket (13 pre-existing/environmental Windows failures plus 3 load-sensitive perf-timing tests)."
    remediation: "Separate tickets for the Windows backslash-path and temp-dir probe failures; none needed for this ticket."
  failure_report_structured: true

### 2026-10-06 16:12 — commit (status: ok)
feedback-id: (submit-failed)
Committed: "fix(ticket-creation): stop generated tickets starting with status-checker"
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
