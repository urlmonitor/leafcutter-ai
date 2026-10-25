---
title: "AC store: the components enum in ac_store_schema.json lags docs/components.json"
status: todo
components:
  - ac_store
created: 2026-10-03
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: schema
risk_surface: internal
tags:
  - ac-store
  - schema
  - drift
last_updated: 2026-10-03
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# AC store: the components enum in ac_store_schema.json lags docs/components.json

## Actor / Goal
In order that ACs can name every registered component, we need the `components` enum in
`config/ac_store_schema.json` to stay in step with `docs/components.json`, the single canonical
component registry, so that a valid component id is never rejected.

## Context
- **Live reproduction (2026-10-03):** the product-owner stage on branch
  `ac-authoring/reusable-criteria-store` wrote DK-300 and DK-300f with
  `components: [decision_kernel, colony_memory]`.
  - `scripts/ac_store/validate_ac_schema.py` rejected `colony_memory` as not in the enum.
  - The PO removed it and recorded the drift in the ACs' notes, so those ACs now under-declare
    their components.
- **Measured drift:** `docs/components.json` has `colony_memory` and `epic_retrospective`, but
  the enum lacks both. Nothing in the enum is unknown to `docs/components.json`.
- The schema's own description of `components` says every value must be a component id declared
  in `docs/components.json`, the shared registry. The enum is a second copy that nothing keeps in
  sync.

## Scope (no acceptance criteria by user decision)
- Remove the duplicate: validate `components` values against `docs/components.json` at
  validation time. If the enum must stay for tooling, generate it from `docs/components.json`
  and have a test that fails on any difference.
- Add `colony_memory` back to DK-300 and DK-300f once the fix lands (their notes say so).
- Tests: a component added to `docs/components.json` is accepted without editing the schema; an
  unknown id is still rejected.

## Out of Scope
- Changing the component registry itself.

## Comments

## Implementation Tasks
### test-writer
- [ ] Sync test plus the accept and reject cases.
### python-coder
- [ ] Registry-backed validation (or a generated enum) in the AC schema validator and the commit hook.

## Risk & Safety
- Touches money? No.
- Touches data? Schema only; no AC changes beyond the two follow-ups.
- Reversibility? Fully reversible.
