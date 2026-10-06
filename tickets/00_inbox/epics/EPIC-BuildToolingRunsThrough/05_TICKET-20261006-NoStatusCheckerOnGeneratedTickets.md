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
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
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
- [ ] Write `unit_tests/test_guardrail_matrix_status_checker.py`, loading the real `config/guardrail_gates.yaml`, with the four tests above.

### python-coder
- [ ] Edit `config/guardrail_gates.yaml`: lines 177, 190 and 197, and the flow-change gate at 322-328 (mandatory_agents and phase_constraint text).
- [ ] Run `python scripts/build.py` and stage the tracked outputs.

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/test_generate_ticket_from_ac.py`, `unit_tests/test_bo_2200*` and the new file. pr-reviewer confirms that no other config or doc lists the removed cells.

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
