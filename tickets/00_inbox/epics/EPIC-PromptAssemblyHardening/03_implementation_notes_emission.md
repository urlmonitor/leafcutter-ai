---
title: "Ticket generator emits Implementation Notes; dispatch stays thin and points to it"
status: in_progress
components:
  - ticket_creation_pipeline
  - supervisor_system
created: 2026-07-08
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
test_constraints: unit_only
complexity: medium
ac_coverage: 0/6
files_touched:
  - scripts/ac_store/generate_ticket_from_ac.py
  - templates/workflows-js/build-ticket.js
  - unit_tests/prompt_assembly/test_implementation_notes_emission.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 03: Ticket generator emits Implementation Notes; dispatch stays thin

## Actor / Goal

In order that a task-specific implementation spec travels on one owning channel
(Channel 8, the ticket body) instead of being re-typed off-channel into a dispatch
prompt, the ticket generator must write a structured `## Implementation Notes` section
from the AC's `it_requirements`, and the deterministic dispatch must hand the agent a
thin pointer that tells it to read the ticket first.

## Context

`scripts/ac_store/generate_ticket_from_ac.py` currently emits `## Actor / Goal`,
`## Context`, `## Acceptance Criteria`, and a `## Test Requirements` stub — but no
section carrying the implementation spec. `templates/workflows-js/build-ticket.js`
(line ~266) emits a thin prompt (`You are the ${phaseName} phase agent for ticket:
${ticketPath}. Execute your phase. Files touched: ...`) that does not even instruct the
agent to read the ticket. This is the root-cause vacuum from
[EPIC-PromptAssemblyHardening](./Master_Plan.md): the spec has no home, so it gets
hand-typed and drifts.

The dispatch must stay thin — the fix is a pointer, **not** inlining the spec into the
prompt (that would recreate the drift). See
[docs/architecture/components/build-ticket-workflow-dispatch.md](../../../../docs/architecture/components/build-ticket-workflow-dispatch.md).

## AC References

Implements L1 **BO-2000c** and its leaves: BO-2000c-1, BO-2000c-1-i, BO-2000c-2,
BO-2000c-3, BO-2000c-3-i, BO-2000c-4. Canonical source: the BO-2000 AC folder.

## Acceptance Criteria

- [ ] AC-1 (BO-2000c-1): when an AC carries `it_requirements`, the generator writes a `## Implementation Notes` section into the ticket body reproducing that spec verbatim (config-schema fragment, resolved reference-file path, N-location rule, required skills, post-write commands).
- [ ] AC-2 (BO-2000c-1-i): when an AC has no `it_requirements`, the generator omits the section (no empty stub).
- [ ] AC-3 (BO-2000c-2): the emitted section is well-formed and placed consistently in the body so a phase agent can locate it.
- [ ] AC-4 (BO-2000c-3 / -3-i): the `build-ticket.js` dispatch string instructs the agent to read the ticket before starting, and otherwise remains thin (no inlined spec beyond phase name, ticket_path, files_touched).
- [ ] AC-5 (BO-2000c-4): the thin-dispatch behavior is preserved for the deterministic `.js` path (no regression to the payload it passes).

## Test Requirements

```yaml
tests:
  - name: test_generator_emits_implementation_notes_when_it_requirements_present
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    covers: [BO-2000c-1, BO-2000c-2]
    asserts: "given an AC record with it_requirements, the generated ticket body contains a ## Implementation Notes section reproducing each field verbatim."
  - name: test_generator_omits_section_when_absent
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    covers: [BO-2000c-1-i]
    asserts: "given an AC record without it_requirements, the generated body has no ## Implementation Notes section."
  - name: test_dispatch_prompt_instructs_read_ticket_and_stays_thin
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    covers: [BO-2000c-3, BO-2000c-3-i, BO-2000c-4]
    asserts: "build-ticket.js dispatch string contains a read-the-ticket instruction and carries only phase name, ticket_path, files_touched (no inlined spec)."
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Sign-offs

- [x] test-writer — 2026-07-08 11:30
- [x] python-coder — 2026-07-08 11:45
- [x] test-runner — 2026-07-08 12:00
- [x] pr-reviewer — 2026-07-08 12:10
- [ ] commit
- [ ] pull-request

## Comments

### 2026-07-08 11:30 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
  ac_ids_covered: [BO-2000c-1, BO-2000c-1-i, BO-2000c-2, BO-2000c-3, BO-2000c-3-i, BO-2000c-4]
red_baseline:
  - test_name: test_generator_emits_implementation_notes_when_it_requirements_present
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    error: "AssertionError: '## Implementation Notes' not found in ticket body when AC record carries it_requirements."
  - test_name: test_generator_omits_section_when_absent
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    error: "(passes immediately — omit-when-absent is trivially true before feature exists)"
    note: "passes immediately — may be under-specified; acceptable because the negative case is trivially correct until implementation lands"
  - test_name: test_dispatch_prompt_instructs_read_ticket_and_stays_thin
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    error: "AssertionError: Regex 'read the ticket' not found in dispatch excerpt from build-ticket.js line 266."
Created unit_tests/prompt_assembly/test_implementation_notes_emission.py with 3 test stubs. Raw run (AC enforcement plugin disabled): 2 FAILED, 1 PASSED. With plugin: 2 XFAILED, 1 PASSED (ACs in progress). Coders must make tests 1 and 3 green by adding ## Implementation Notes emission to generate_ticket_from_ac.py and adding read-the-ticket instruction to build-ticket.js dispatch string.

### 2026-07-08 11:45 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  implementation_notes_emission: true
  dispatch_string_updated: true
  existing_tests_regression_free: true
Added `_build_implementation_notes_section()` helper to `generate_ticket_from_ac.py` — serialises `it_requirements` dict to a YAML code block inside `## Implementation Notes`; omits section entirely when field is absent. Integrated the call in `_build_ticket_body()` between `## Test Requirements` and `## Sign-offs`. Added "Read the ticket before starting." to the phase dispatch string in `build-ticket.js` line 266. All 45 existing tests in `test_generate_ticket_from_ac.py` still pass.

### 2026-07-08 12:00 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  new_tests_green: true
  regression_suite_green: true
All 3 new tests in `unit_tests/prompt_assembly/test_implementation_notes_emission.py` pass. Broader regression: 45 tests in `test_generate_ticket_from_ac.py` + 8 in `test_build_ticket_workflow.py` = 53 tests all green.

### 2026-07-08 12:10 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac1_satisfied: true
  ac2_satisfied: true
  ac3_satisfied: true
  ac4_satisfied: true
  ac5_satisfied: true
All 5 ACs satisfied. `_build_implementation_notes_section()` correctly emits/omits the section, section is consistently placed, dispatch string is thin with read-ticket pointer, no regression in build-ticket.js tests. Ruff clean. Approving for commit.

## Implementation Tasks

### python-coder
- [x] Extend `generate_ticket_from_ac.py` to emit a `## Implementation Notes` section from `it_requirements` (verbatim; omit when absent). Read the file fully before editing.
- [x] Add the "Read the ticket before starting." instruction to the `build-ticket.js` dispatch string; keep it otherwise thin.

## Risk & Safety

- Touches money? No.
- Touches data? No — generator + dispatch string; additive.
- Reversibility? Fully reversible via git.
