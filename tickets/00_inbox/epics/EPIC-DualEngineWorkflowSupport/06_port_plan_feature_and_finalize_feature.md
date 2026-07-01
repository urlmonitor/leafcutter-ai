---
title: "Port plan-feature.js and finalize-feature.js to E2 canonical form"
status: todo
components:
  - supervisor_system
  - ac_store
created: 2026-07-01
depends_on:
  - 03_canonical_e2_contract_and_adr.md
  - 04_build_time_variant_transform.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/finalize-feature.js
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

# 06: Port plan-feature.js and finalize-feature.js to E2 canonical form

## Actor / Goal

In order for `/plan-feature` and `/finalize-feature` to actually run
deterministically, their scripts must be authored in the E2 canonical contract
so the live engine executes them instead of silently no-opping.

## Context

Both are large E1-only scripts (`export run()`, `agent({agentType,input})`) →
inert under E2. Port to top-level-body + `agent(prompt, {agentType, schema})` per
the ticket-03 template. finalize-feature is a declared **leaf** (calling
`workflow()` must throw) — that invariant must survive the port. plan-feature has
a critical no-commit-to-main guard and user-confirmation gates that must remain
fail-closed (do not rely on schema validation to catch safety checks). Replace
`Date.now()` (temp-worktree naming) and `Math.random()` (run-ids) with the
ticket-03 conventions. Gated by the ticket-02 zero-dispatch guard.

## Acceptance Criteria

```gherkin
Scenario: plan-feature runs under E2
  Given the ported plan-feature.js
  When executed by the E2 engine
  Then its top-level body runs ac-triage -> PO -> BA -> IT-PO with the
   confirmation gates intact, dispatching >= 1 agent (passes the ticket-02 guard).

Scenario: finalize-feature runs under E2 and stays leaf
  Given the ported finalize-feature.js
  When executed by the E2 engine
  Then its top-level body runs the finalize steps, and any workflow() call still
   throws (leaf invariant preserved).

Scenario: safety guards remain fail-closed
  Given the ported plan-feature.js
  Then the no-commit-to-main check and confirmation gates are explicit in code,
   not delegated to schema validation.

Scenario: banned globals removed
  Then neither ported script mentions Date.now()/new Date()/Math.random()
   (E2 rejects them); timestamps/ids come from the ticket-03 conventions.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Port plan-feature.js to E2 canonical; keep the no-main-commit guard + gates fail-closed
- [ ] Port finalize-feature.js to E2 canonical; preserve the leaf/no-nesting invariant
- [ ] Remove Date.now()/Math.random() usages per ticket-03 conventions
- [ ] Verify both pass the ticket-02 zero-dispatch guard and the ticket-04 e1-emission test

## Risk & Safety
- Touches money? No.
- Touches data? finalize-feature performs merges/PR actions when run — the port must not change its confirmation gates. Ports are gated by the harness and reviewed before merge.
