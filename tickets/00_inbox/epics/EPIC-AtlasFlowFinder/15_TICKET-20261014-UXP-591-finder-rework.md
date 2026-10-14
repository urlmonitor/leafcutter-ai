---
advances_current_outcome: true
agents:
  commit: needed
  frontend-coder: needed
  pr-reviewer: needed
  test-writer: needed
change_target:
- code
- ui
complexity: medium
components:
- ux_prototyping
- atlas_frontend
- frontend_coding
created: '2026-10-14'
depends_on:
- 01_TICKET-20261014-UXP-617-1.md
files_touched:
- leafcutter-web/app/flows/page.tsx
- leafcutter-web/components/flows/flow-view-model.ts
- leafcutter-web/components/flows/use-flows-view-state.ts
- leafcutter-web/components/flows/flow-history.ts
- leafcutter-web/lib/flow-url.ts
priority: medium
requires_adr: false
requires_diagram: false
risk_surface: contract_boundary
roadmap_phase: phase_1
source_ac: UXP-591-1-i
status: todo
title: Rework the six UXP-591 behaviours the finder changed
---

# Rework the six UXP-591 behaviours the finder changed

## Actor / Goal

As a person using the Atlas, I want the canonical-URL behaviours shipped in PR #1176 to match the finder, so that bare /flows opens the finder and a filter change never swaps the flow I am viewing.

## Context

Hand-written because the generator refuses a second ticket for an AC that already has one: these six ACs keep their original tickets in `EPIC-AFlowsCanonicalAddressOpensTheAtlasOn` (built in PR #1176). Their criteria and technical fields were rewritten for the finder in PR #1216 (BA commit 6b32f0c7e, IT-PO commit bed276966) and re-approved at medium priority. The code and tests from PR #1176 still implement the old behaviour, so they must change.

ACs (all in `docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/`):

- `UXP-591-1-i` — bare /flows opens the finder, not a flow (no redirect, no default-entry render).
- `UXP-591-4` — no drawer on the finder; /flows is never rewritten to a step address.
- `UXP-591-4-ii` — the bare-/flows close clause is removed.
- `UXP-591-5-ii` — Back/Forward sessions start from a flow's own address; a /flows entry pops to the finder; the 'Outside the current filters' notice is derived on restore.
- `UXP-591-5-iii` — a filter change keeps the drawn flow (replace with the same URL, `?step=` kept) and shows 'Outside the current filters'; no re-pick.
- `UXP-591-5-v` — on 'Flow not found' a filter change keeps the notice and address, draws nothing, and only re-lists the selector (owner decision, 2026-10-14).

## Acceptance Criteria

- [ ] AC-1: Every criterion of the six ACs above holds, as written in their YAML.
- [ ] AC-2: The PR #1176 tests that asserted the old behaviour are rewritten to the new criteria; no test asserts a default entry flow on bare /flows or a filter re-pick.

## Test Requirements

```yaml
tests:
  - name: uxp_591_1_i_bare_flows_is_the_finder
    path: leafcutter-web/__tests__/uxp-591-1/uxp-591-1-i.test.ts
    framework: vitest
    covers: [UXP-591-1-i]
  - name: uxp_591_4_no_drawer_on_finder
    path: leafcutter-web/__tests__/uxp-591-4/uxp-591-4.test.ts
    framework: vitest
    covers: [UXP-591-4, UXP-591-4-ii]
  - name: uxp_591_5_filter_keeps_flow_and_restore
    path: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    framework: vitest
    covers: [UXP-591-5-ii, UXP-591-5-iii, UXP-591-5-v]
```

## Implementation Notes

See each AC's `it_requirements`. Known test files to rewrite: `__tests__/uxp-591-1/uxp-591-1-i.test.ts`, `__tests__/uxp-591-4/uxp-591-4.test.ts`, `uxp-591-4-ii.test.ts`, `__tests__/uxp-591-5/uxp-591-5-ii.test.ts`, `uxp-591-5-iii.test.ts`, `uxp-591-5-v.test.ts`; check `uxp-591-5.test.ts`, `helpers/flow-history-nav.ts` and `components/flows/__tests__/uxp-591-1.test.tsx`.

## Comments
