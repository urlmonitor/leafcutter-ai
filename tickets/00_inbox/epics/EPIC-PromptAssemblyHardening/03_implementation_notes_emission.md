---
title: "Ticket generator emits Implementation Notes; dispatch stays thin and points to it"
status: todo
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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### python-coder
- [ ] Extend `generate_ticket_from_ac.py` to emit a `## Implementation Notes` section from `it_requirements` (verbatim; omit when absent). Read the file fully before editing.
- [ ] Add the "Read the ticket before starting." instruction to the `build-ticket.js` dispatch string; keep it otherwise thin.

## Risk & Safety

- Touches money? No.
- Touches data? No — generator + dispatch string; additive.
- Reversibility? Fully reversible via git.
