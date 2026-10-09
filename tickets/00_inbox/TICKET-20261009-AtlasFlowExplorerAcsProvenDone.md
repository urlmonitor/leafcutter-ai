---
title: "Atlas flow-explorer ACs marked done are proven by real tests, and UXP-524 reopens"
status: todo
components:
  - ux_prototyping
created: 2026-10-09
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - phantom-done
  - done-proof
  - covers-tags
  - atlas
  - flows
  - bo-2500
last_updated: 2026-10-09
ac_traceability:
  l2:
    - UXP-520
    - UXP-521
    - UXP-522
  l3: []
  ac_path: docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/
files_touched:
  - leafcutter-web/components/flows/__tests__/flows-view.filters.test.tsx
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-520.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-521.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-522.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-524.yaml
agents:
  architect-review: not_needed
  test-writer: needed
  frontend-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
  pull-request: needed
---

# Atlas flow-explorer ACs marked done are proven by real tests, and UXP-524 reopens

## Actor / Goal
In order that the Atlas Flows view's acceptance criteria say "done" only when a test proves it,
we need real, covers-tagged tests for UXP-520, UXP-521 and UXP-522, and UXP-524 reopened until its
link works. Then the done-proof gate stops blocking commits that touch these ACs, and nobody relies
on a cross-link that does not work.

## Context
- **Four done ACs with no proof.** In
  `docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/`, these L2 ACs have
  `work_status: done` and `covered_by: []`. No `# covers:` or `// covers:` tag for any of them
  exists in the repo (checked 2026-10-09):
  - UXP-520 "The Flows view lists flows and renders the selected one as a graph"
    (implemented_by `leafcutter-web/app/flows/page.tsx`, `lib/data/flows.ts`, `lib/data/graph.ts`).
  - UXP-521 "A source toggle filters flows by mock vs real" (`components/flows/flows-view.tsx`).
  - UXP-522 "A kind chooser filters flows by user/data/architecture" (`flows-view.tsx`).
  - UXP-524 "An AC node links to the flows it appears in" (`components/atlas/detail-drawer.tsx`).
- **The gate blocks unrelated commits.** The `check-done-proof` pre-commit hook (BO-2500b, a static
  check that a covers tag exists for every staged done AC) blocked a product-truth commit that only
  touched these ACs' generator-owned `product_truth` back-reference. The explore-flows-in-atlas v5
  flow therefore left its flow-level `mock_data_ref` unset. Its version note says these ACs'
  "missing test coverage is ticketed separately". This is that ticket.
- **No existing test covers UXP-520..522.** No test file imports `FlowsView` (`flows-view.tsx`),
  the `/flows` page or `DetailDrawer`. The nearest tests exercise other ACs:
  - `components/flows/__tests__/flow-explorer.contracts.test.tsx` renders `FlowExplorer` for one
    flow and checks its contract drawer (covers UXP-523-1..3).
  - `components/flows/__tests__/flow-drawer.contracts.test.tsx` covers UXP-523-1..4.
  - `components/flows/__tests__/flow-nodes.decisions.test.tsx` covers UXP-597, 601-603a, 605 and
    605a, and renders `FlowExplorer` only.
  - `lib/data/__tests__/flows.contracts.test.ts` loads a single flow file (UXP-523-1/2).
  - `lib/data/__tests__/graph.decisions.test.ts` tests `buildFlowGraph` for diamonds and AC counts
    (UXP-597..604).

  None of them lists flows, selects between flows, or uses the Source or Kind control. Tagging any
  of them for UXP-520..522 would be tagging for the gate. They are useful only as patterns: the
  `@/lib/data/repo` mock in `flows.contracts.test.ts`, the `ResizeObserver` stub, and
  `flow-decisions.fixture.ts` (`testFlow`, `kind: "user"`, `source: "real"`).
- **The criterion text and the shipped view disagree in three places**
  (`flows-view.tsx` :119-176, :280-312). A test that asserts the criterion text as written would
  fail, and a test that asserts less must not be tagged as if it proved the whole criterion.
  - UXP-520 says "every flow is listed". The list shows only flows that match the current Source,
    Kind and Realization. The flow's own `open` step already says this is "not an unfiltered
    promise that every flow appears at once".
  - UXP-521 says "only mock or only real flows (or all)". The Source control offers only Mock and
    Real. "All" exists only on the Realization control.
  - UXP-522 lists user, data and architecture. The Kind control shows only the kinds that have at
    least one flow for the current source, and falls back to the first available kind.
- **UXP-524 is a phantom done.** The AC drawer emits
  `/flows?flow=<encodeURIComponent(flowId)>&step=<stepId>` (`detail-drawer.tsx` :311). Neither
  `app/flows/page.tsx` nor `flows-view.tsx` reads a query parameter, so the link opens the default
  flow (`DEFAULT_ENTRY = "leafcutter/deliver-a-feature"`), not the linked flow or step.
- **The fix for UXP-524 is already being planned.** `/plan-feature` on branch
  `ac-authoring/ux-prototyping` approved explore-flows-in-atlas v5 on 2026-10-09. Step
  `acStepLink` specifies that the drawer links to `/flows/<flow id>?step=<node id>`. Step
  `openStepLink` opens that flow with the step's drawer open, and branch `legacyRedirect` sends old
  `?flow=` links to it with a 308. Their `implements` lists are still empty; the business-analyst
  derives their ACs next. Step `cross` keeps its UXP-524 link.
- **Parent.** UXP-591 (L1, `covered_by` UXP-520..524) is already `in_progress`, so reopening
  UXP-524 does not invalidate a done parent.
- **Windows.** The pre-commit check is static and runs on Windows. The authoritative proof
  (`verify_done_eligible`: CI's `--mode ci-changed`, and `mark_ac_done.py` with a test root) runs
  the tagged vitest tests. On Windows that launch fails closed with `[WinError 193]` until
  TICKET-20261008-DoneProofLaunchesVitestOnWindows lands (same PR, #1065). Until then, run that
  proof on Linux CI and not on a Windows host.

## AC References
- Proves UXP-520, UXP-521, UXP-522 (adds tests and `covered_by`; may amend criteria text through
  the business-analyst, see AC-1).
- Reopens UXP-524 and links it to the AC the business-analyst derives for explore-flows-in-atlas v5
  step `acStepLink` (and `openStepLink`).

## Acceptance Criteria
- [ ] AC-1: UXP-520, UXP-521 and UXP-522 each have at least one real test, tagged
  `// covers: <id>` and listed in that AC's `covered_by`, that fails if the behaviour breaks.
  Tag an existing test only if it genuinely asserts the behaviour; never tag to satisfy the gate.
  Where the criterion text and the shipped view disagree (see Context), first agree on the behaviour.
  Either the business-analyst amends the criterion to the shipped behaviour, or a follow-up fixes
  the code. Then the test asserts the agreed behaviour in full. `test_required: false` is not used
  to get past the gate.
- [ ] AC-2: UXP-524 goes back to `work_status: in_progress`, or the business-analyst marks it
  `superseded_by` the step-link AC. It does not return to `done` until the AC drawer's "Appears in
  flows" link opens the linked flow, with the linked step's drawer open. It is closed by the AC
  derived for step `acStepLink` (with `openStepLink`) and by that AC's test, which follows the link
  and also carries `// covers: UXP-524`. The planning branch `ac-authoring/ux-prototyping` and its
  derived ACs link back to UXP-524, so the two are not built twice.
- [ ] AC-3: `check-done-proof` passes when the four AC files are staged, with no `--no-verify` and
  no hook skip. The CI check `check_done_proof.py --mode ci-changed` passes for them on Linux.
- [ ] AC-4: The ticket's closing comment states where the done proof was run. While
  TICKET-20261008-DoneProofLaunchesVitestOnWindows is open, `verify_done_eligible` for these
  vitest-covered ACs cannot pass on Windows, so it runs on Linux CI. Re-run it on Windows once
  that ticket lands.

## Test Requirements

```yaml
tests:
  - name: source_toggle_lists_only_flows_of_the_chosen_source
    location: leafcutter-web/components/flows/__tests__/flows-view.filters.test.tsx
    type: unit
    covers: [AC-1]
    description: |
      // covers: UXP-521. Render FlowsView with a fixture of mock and real flows across kinds.
      Choosing Mock lists only the mock flows; choosing Real lists only the real flows. Asserts
      flow names in the per-flow selector, not internal state. Fails if the `f.source === source`
      predicate is removed.
  - name: kind_chooser_lists_only_flows_of_the_chosen_kind_and_renders_the_selected_graph
    location: leafcutter-web/components/flows/__tests__/flows-view.filters.test.tsx
    type: unit
    covers: [AC-1]
    description: |
      // covers: UXP-522. With flows of kinds user, data and architecture in one source, each
      Kind choice lists only flows of that kind. Selecting a listed flow renders its graph (its
      step labels appear, another flow's do not). Asserts that only kinds with flows are offered,
      if that is the agreed criterion.
  - name: flows_view_reaches_every_flow_and_renders_the_selected_one_as_a_graph
    location: leafcutter-web/components/flows/__tests__/flows-view.filters.test.tsx
    type: unit
    covers: [AC-1]
    description: |
      // covers: UXP-520. Every fixture flow is listed under some Source and Kind choice (the
      union equals the fixture set), and the selected flow renders as a graph built from its
      steps and branches (a branch's decision node appears). If the agreed criterion keeps
      "read straight from the store", one case renders the /flows page with the
      `@/lib/data/repo` mock serving two or more real flow files, as flows.contracts.test.ts does.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | flows-view.filters.test.tsx (three tests above) | UXP-520/521/522 `covered_by`; criteria amended if needed | |
| AC-2 | step-link AC's test (planning branch) | UXP-524 `work_status` / `superseded_by` | |
| AC-3 | `check-done-proof` on staged AC files; `--mode ci-changed` on CI | | |
| AC-4 | closing comment | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Decide each criterion mismatch with the business-analyst (amend the text, or file a code fix)
  before writing assertions.
- [ ] Write `flows-view.filters.test.tsx` with the three tests and their `// covers:` tags; reuse the
  `ResizeObserver` stub and a multi-flow fixture.
- [ ] Confirm that each test fails when its filter or selection predicate in `flows-view.tsx` is
  broken (mutation check), then restore it.
- [ ] Add the test ids to `covered_by` on UXP-520, UXP-521 and UXP-522 in the house format
  (`"<path>::<test name>"`).
- [ ] Set UXP-524 to `in_progress` (or `superseded_by`), with a dated reason. Ask the
  `ac-authoring/ux-prototyping` run to reference UXP-524 from the `acStepLink` AC.
- [ ] Stage the four AC files and confirm `check-done-proof` passes; record where the
  `verify_done_eligible` proof ran.

## Risk & Safety
- Touches money? No.
- Touches data? Only AC store fields (`covered_by`, `work_status`, possibly criterion text through
  the business-analyst). Production code changes only if a mismatch is resolved in favour of the
  criterion, and that goes to its own ticket.
- Reversibility: revert the commit.

## Out of Scope
- Building the canonical flow URLs, the step link or the legacy redirect (the
  `ac-authoring/ux-prototyping` plan and its build).
- Making the done proof launch vitest on Windows (TICKET-20261008-DoneProofLaunchesVitestOnWindows).
- Setting the explore-flows-in-atlas flow-level `mock_data_ref` (it can follow once this lands).
