---
title: "A code ticket cannot be authored or dispatched without a Test Requirements section"
status: todo
components:
  - ticket_creation_pipeline
  - supervisor_system
created: 2026-07-08
depends_on:
  - 03_implementation_notes_emission.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
test_constraints: unit_only
complexity: medium
ac_coverage: 0/3
files_touched:
  - scripts/commit_guardian/check_ticket_test_requirements.py
  - templates/workflows-js/build-ticket.js
  - unit_tests/prompt_assembly/test_test_requirements_guard.py
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

# 05: A code ticket cannot be authored or dispatched without a Test Requirements section

## Actor / Goal

In order that the failure mode where `test-writer` is skipped and the coder self-writes
its own phantom tests can no longer happen, a code ticket must carry a populated
`## Test Requirements` section: an empty/absent section on a code ticket is blocked at
authoring, and the supervisor refuses to dispatch the coder phase for such a ticket.

## Context

`EPIC-Phase1ReadyHardening/04_HookParityCheck` had an empty test-requirements block, so
`test-writer` self-skipped and `python-coder` was told to write its own tests —
violating its Test-Delegation rule and producing phantom coverage (a test identical to
another AC's code path). This ticket closes that hole. Non-code tickets keep the
documented docs-only skip behavior. A slice of
[EPIC-PromptAssemblyHardening](./Master_Plan.md).

Depends on ticket 03 because both edit `templates/workflows-js/build-ticket.js`; 03
lands the thin-dispatch/read-first change first, then this ticket adds the dispatch
refusal on top.

## AC References

Implements L1 **BO-2000e** and its leaves: BO-2000e-1, BO-2000e-1-i, BO-2000e-2.
Canonical source: the BO-2000 AC folder.

## Acceptance Criteria

- [ ] AC-1 (BO-2000e-1): a code ticket (agents map has a coder `needed`) with an empty or absent `## Test Requirements` / `tests: []` is blocked at authoring with an actionable reason.
- [ ] AC-2 (BO-2000e-1-i): a non-code ticket (docs-only / config-only, no coder needed) is NOT blocked — the documented skip behavior is preserved.
- [ ] AC-3 (BO-2000e-2): the deterministic dispatch (`build-ticket.js`) refuses to dispatch the coder phase for a code ticket whose `## Test Requirements` is empty/absent, surfacing a structured blocker rather than proceeding.

## Test Requirements

```yaml
tests:
  - name: test_authoring_blocks_code_ticket_without_test_requirements
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    covers: [BO-2000e-1]
    asserts: "the authoring guard rejects a code ticket with empty/absent Test Requirements and emits an actionable reason."
  - name: test_authoring_allows_noncode_ticket
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    covers: [BO-2000e-1-i]
    asserts: "a docs-only/config-only ticket with no coder needed passes the guard."
  - name: test_dispatch_refuses_coder_without_test_requirements
    file: unit_tests/prompt_assembly/test_test_requirements_guard.py
    covers: [BO-2000e-2]
    asserts: "the build-ticket.js dispatch logic returns a structured blocker (does not dispatch the coder) for a code ticket lacking Test Requirements."
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### python-coder
- [ ] Add an authoring guard (`check_ticket_test_requirements.py` pre-commit hook, or extend the ticket-frontmatter guard) that blocks a code ticket with empty/absent Test Requirements; leave non-code tickets untouched. Register it via `create-hook`.
- [ ] Add the coder-dispatch refusal to `build-ticket.js` for such tickets (structured blocker). Read the file fully before editing.

## Risk & Safety

- Touches money? No.
- Touches data? No — adds a guard + dispatch check; blocks only invalid code tickets.
- Reversibility? Fully reversible via git.
