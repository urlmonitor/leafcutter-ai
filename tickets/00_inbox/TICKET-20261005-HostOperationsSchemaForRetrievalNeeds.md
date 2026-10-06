---
title: "Kernel tests: the host-operation test tables include host.retrieval_needs"
status: todo
components:
  - decision_kernel
created: 2026-10-05
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - testing
  - host-operation
last_updated: 2026-10-05
agents:
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel tests: the host-operation test tables include host.retrieval_needs

## Actor / Goal
In order that DK-400c-1 can add `host.decompose_goal` to a green test file, we need the
host-operation test-support tables to cover every operation the registry binds, so that
`test_every_host_capability_of_the_design_has_an_operation` passes on main again.

## Context
- **Failing on main** (CI run 37357952636, main 28b6168c; baseline row 1 in
  `docs/analysis/2026-10-05-dk400-dk500-build-test-baseline.md`):
  `tests/kernel/capabilities/test_host_operations.py::TestCompiler::test_every_host_capability_of_the_design_has_an_operation`
  asserts `set(OPERATIONS) == set(SCHEMAS)` (line 146).
- **Cause:**
  - `kernel/capabilities/host/registry.py:24` `OPERATIONS` gained `host.retrieval_needs`
    (`kernel/capabilities/host/retrieval_needs.py`, operation `interpret_retrieval_needs`) in commit
    6ae01413d (#1009, the isolated retrieval-needs experiment).
  - The test-support table `tests/kernel/capabilities/host_support.py:53` `SCHEMAS`, and its
    companion `REQUESTS`, were not extended.
- **Why now:** decision dec-9925ebf1895222f4, Step 0. DK-400c-1 (DK-400 epic E1) extends this test
  file with `host.decompose_goal`, so it must not start on a red file.

## Scope (no acceptance criteria; a test-support repair)
- Add the `host.retrieval_needs` request and output schema ids (from
  `kernel/contracts/retrieval_needs.py` and the registry entry) to `SCHEMAS` and `REQUESTS` in
  `tests/kernel/capabilities/host_support.py`, with a minimal valid request fixture.
- `test_host_operations.py` passes in full. `TestBootstrapBindings` also iterates `SCHEMAS`, so the
  new row must bind to its executor.
- If the retrieval-needs operation is meant to stay out of the registry, remove it from
  `OPERATIONS` instead. Check `config/capability_registry.json` and the #1009 notes first, and say
  which applies.

## Out of Scope
- Any change to the retrieval-needs behaviour itself.

## Comments

## Implementation Tasks
### python-coder
- [ ] Extend `SCHEMAS` and `REQUESTS` in `tests/kernel/capabilities/host_support.py` for `host.retrieval_needs`.
- [ ] Run `tests/kernel/capabilities/test_host_operations.py` green.

## Risk & Safety
- Touches money? No.
- Touches data? No; test-support tables only.
- Reversibility? Fully reversible.
