---
advances_current_outcome: true
agents:
  commit: needed
  frontend-coder: needed
  pr-reviewer: needed
  test-writer: signed_off
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

### 2026-10-14 19:00 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_rewritten_vitest: true
  no_test_asserts_default_flow_or_repick: true
  not_yet_built_behaviour_red: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "dataset FlowNavigation sessions (filter-replace, drawer-in-history, drill-and-return) and the filter/pop handlers in components/flows/"
    consuming_side: "the Flows view and the not-found boundary rendered through app/flows/[...id] and app/flows/page.tsx, driven over jsdom's real history"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "default exports of leafcutter-web/app/flows/page.tsx, app/flows/[...id]/page.tsx and app/flows/[...id]/not-found.tsx, plus the default export of middleware.ts; no CLI, hook or workflow step fronts them"
red_baseline:
  - test_name: "the default-entry constant and its flow id are gone from the page, the view model and the url helper"
    file: leafcutter-web/__tests__/uxp-591-1/uxp-591-1-i.test.ts
    kind: assertion
    error: "AssertionError: expected [ …(3) ] to deeply equal []"
  - test_name: "Back onto a /flows entry shows the finder with no flow drawn, and Forward returns the flow"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-ii.test.ts
    kind: assertion
    error: "AssertionError: expected [] to deeply equal [ '28 flows' ]"
  - test_name: "replays the filter-replace session from atlas-flows.mock.json"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-ii.test.ts
    kind: assertion
    error: "AssertionError: nav-filter-replace-5 address: expected '/flows/leafcutter/define-a-feature' to be '/flows/leafcutter/how-acs-are-built?s…' // Object.is equality"
  - test_name: "Realization Spec keeps how-acs-are-built, its breadcrumb and drawer, keeps ?step=code and two entries, and shows the notice"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    kind: assertion
    error: "AssertionError: expected '/flows/leafcutter/define-a-feature' to be '/flows/leafcutter/how-acs-are-built?s…' // Object.is equality"
  - test_name: "Back returns deliver-a-feature at Real, User, All with no notice; Forward brings back Spec and the notice"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    kind: assertion
    error: "AssertionError: expected 'Product truth · LeafcutterDefine a fe…' to contain 'Outside the current filters'"
  - test_name: "replays filter-replace seq 1 to 7, including the notice records -5 and -7 and the notice-free -6"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    kind: assertion
    error: "AssertionError: nav-filter-replace-5 address: expected '/flows/leafcutter/define-a-feature' to be '/flows/leafcutter/how-acs-are-built?s…' // Object.is equality"
  - test_name: "Source Mock keeps the drawn flow and shows the notice naming the three filter labels"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    kind: assertion
    error: "AssertionError: expected 'Product truth · Fern & FigCheckout & …' to contain 'Outside the current filters'"
  - test_name: "Kind Data keeps the drawn flow and shows the notice naming the three filter labels"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    kind: assertion
    error: "AssertionError: expected 'Product truth · LeafcutterHow an acce…' to contain 'Outside the current filters'"
  - test_name: "Realization Spec keeps the drawn flow and shows the notice naming the three filter labels"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    kind: assertion
    error: "AssertionError: expected 'Product truth · LeafcutterDefine a fe…' to contain 'Outside the current filters'"
  - test_name: "no notice while the filters still fit the entry flow: Built or All, and again once they match"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    kind: assertion
    error: "AssertionError: expected 'Product truth · LeafcutterDefine a fe…' to contain 'Outside the current filters'"
  - test_name: "drawer actions leave it on screen; picking a flow the filters list pushes an entry and clears it"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-iii.test.ts
    kind: assertion
    error: "AssertionError: expected 'Product truth · LeafcutterDefine a fe…' to contain 'Outside the current filters'"
  - test_name: "Kind Architecture keeps the notice, the address and one entry, and the selector lists only product-truth-architecture"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-v.test.ts
    kind: assertion
    error: "AssertionError: expected [ …(2) ] to deeply equal [ Array(1) ]"
  - test_name: "Source Mock re-lists the selector the same way and still draws nothing"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-v.test.ts
    kind: assertion
    error: "AssertionError: expected false to be true // Object.is equality"
  - test_name: "picking Product-truth in the leafcutter architecture pushes its canonical address with a one-flow breadcrumb"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-v.test.ts
    kind: assertion
    error: "AssertionError: expected [ …(2) ] to deeply equal [ Array(1) ]"
  - test_name: "Back from there returns the 'Flow not found' entry with the Kind filter at Architecture"
    file: leafcutter-web/__tests__/uxp-591-5/uxp-591-5-v.test.ts
    kind: assertion
    error: "AssertionError: expected [ …(2) ] to deeply equal [ Array(1) ]"
Rewrote uxp-591-1-i, uxp-591-4, uxp-591-4-ii, uxp-591-5-ii, uxp-591-5-iii and uxp-591-5-v (and extended helpers/flow-history-nav.ts replayRows with the Realization filter and the scope_notice check). Tests of behaviour that already holds (the finder on bare /flows, no drawer on the finder, sessions starting at a flow address, drawer-in-history) are green; the 15 red tests need the keep-flow filter change with its derived notice, the keep-notice not-found filter change, the finder pop entry and the removal of the default-entry constant. Feedback script not run (no Python in this build).
