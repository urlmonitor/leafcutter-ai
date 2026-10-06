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
  python-coder: signed_off
  test-runner: signed_off
  pr-reviewer: signed_off
  commit: signed_off
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

## Test Requirements

The tests already exist and one of them is red on main (baseline row 1), so the red baseline is
real. The coder makes them green; no new test is written.

```yaml
tests:
- name: test_every_host_capability_of_the_design_has_an_operation
  file: tests/kernel/capabilities/test_host_operations.py
  covers: []
  asserts: 'Existing test, failing on main at 28b6168c and 5bf8a7c9: set(OPERATIONS) == set(SCHEMAS).
    After the fix the test-support tables list host.retrieval_needs (or OPERATIONS no longer does,
    if the operation is meant to stay out of the registry), and the assertion holds without
    weakening it.'
  framework: unittest
  type: behavioral
  angle: real_artifact
- name: test_each_host_descriptor_gets_its_operation_and_refuses_to_execute
  file: tests/kernel/capabilities/test_host_operations.py
  covers: []
  asserts: 'Existing test, passing today: every SCHEMAS entry binds to its own operation executor
    from the real config/capability_registry.json. It still passes with the new host.retrieval_needs
    row, so the row is bound and not just listed.'
  framework: unittest
  type: behavioral
  angle: real_artifact
```

## Comments

### 2026-10-06 12:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Retrieval-needs stays in OPERATIONS: it is deliberately absent from config/capability_registry.json
(exposed only by experiment registries, integrations/retrieval_needs_llm.py), so it is added to the
test tables instead. Changes: `host_support.py` adds REQUESTS/SCHEMAS rows and `EXPERIMENT_ONLY`;
`test_host_operations.py` binding test iterates `set(SCHEMAS) - EXPERIMENT_ONLY` (the real registry
has no descriptor to bind; the equality assertion is unchanged); `host_rigs.py` adds KINDS,
OPERATIONS, PAYLOADS, RESPONSES rows so the graph tests that iterate SCHEMAS run the new operation.
Results: test_host_operations 15 passed; interaction + capabilities + formulate_routing green.

### 2026-10-06 12:30 — test-runner (status: ok)
feedback-id: fb_2026-10-06_90ec6efc
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Ran tests/kernel/capabilities + tests/kernel/interaction: 250 passed, 78 subtests passed (310s). test_host_operations.py alone: 15 passed. No failures.

### 2026-10-06 13:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-06_2b6279a3
Reviewed diff (host_support.py, test_host_operations.py, host_rigs.py). No high or medium findings. Equality assertion unchanged; binding test excludes EXPERIMENT_ONLY, justified because the registry omits host.retrieval_needs. All edited files parse. Suppressed: 0 low. Escalation: none (medium count 0).

### 2026-10-06 14:00 — commit (status: ok)
feedback-id: fb_2026-10-06_5078f167
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "test(kernel): add host.retrieval_needs to host-operation test tables"; staged files: host_support.py, test_host_operations.py, host_rigs.py, this ticket.

## Implementation Tasks
### python-coder
- [x] Extend `SCHEMAS` and `REQUESTS` in `tests/kernel/capabilities/host_support.py` for `host.retrieval_needs`.
- [x] Run `tests/kernel/capabilities/test_host_operations.py` green.

## Risk & Safety
- Touches money? No.
- Touches data? No; test-support tables only.
- Reversibility? Fully reversible.
