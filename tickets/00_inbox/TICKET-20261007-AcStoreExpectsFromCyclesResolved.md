---
title: "AC store: delete the spurious edge in each live depends_on / expects_from cycle"
status: todo
components:
  - ac_store
created: 2026-10-07
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target:
  - docs
  - code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - ac-store
  - dependencies
  - data-fix
  - epic-generation
last_updated: 2026-10-07
files_touched:
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500c-1.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500c-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400a-1-i.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-3-ii.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-5-iii.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-2.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900b-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900b-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900c-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900c-4.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-2.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-vii.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-viii.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-1900-safe-migration/ACD-1900b-5-i.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500d-1.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500d-3.yaml
  - docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-5.yaml
  - unit_tests/ac_store/test_ac_store_ordering_graph_has_no_live_cycle.py  # new
agents:
  business-analyst: needed
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# AC store: delete the spurious edge in each live depends_on / expects_from cycle

## Actor / Goal
In order that `goal_to_epic` can generate an epic for every live AC tree, we need each remaining
live cycle between `depends_on` and `expects_from` resolved in the AC store. A person decides which
edge is spurious and deletes it, so the generator never chooses an edge to drop and never stops on
a cycle.

## Context
- **Decision.** Decision Kernel dec-46476988badbd5e6 (run run-e02f770927304a29), chosen by the user
  on 2026-10-07: "Parent link yields, other cycles fail naming the edges, plus a data-fix ticket".
  This is the data-fix ticket.
- **Build after EPIC-BuildToolingRunsThrough ticket 08 lands.** Ticket 08
  (`tickets/00_inbox/epics/EPIC-BuildToolingRunsThrough/08_TICKET-20261006-ExpectsFromEdgesGetEpicPrefixes.md`)
  makes `goal_to_epic` order by `depends_on` plus `expects_from`.
  - A child's `depends_on` on its own structural parent (`ac_parent_id.derive_parent_id`) yields
    when the parent's `expects_from` names that child.
  - Every other cycle fails generation. The error has one line per edge:
    `<owner> -> <prerequisite> (<depends_on|expects_from>, parent-link: <true|false>)`.
  - This ticket's test imports ticket 08's ordering code, so it cannot be built before ticket 08 merges.
    It is not listed in `depends_on` because ticket 08 lives in another folder.
  - With ticket 07 (`--ids` honours `--dry-run`) also merged, each group can be reproduced without
    writing anything: `python scripts/goal_to_epic.py --ids <members> --dry-run`.
- **Scope: the 6 live groups.** An independent review found 15 cyclic groups in the store, 10 of them
  live. Seven exist only because of the parent-link shape, which ticket 08 resolves in code. Ticket
  08's coder replayed the merged rule over the real store: 9 groups remain, 6 of them live. The edges
  below come from a replay at ed2190fd3, written in ticket 08's format. Every one has
  `parent-link: false`. Confirm them against ticket 08's own output.

  | # | Group | Shape | Edges (file:line) |
  |---|-------|-------|-------------------|
  | 1 | ACD-2500c-1 / ACD-2500c-3 | two-way handshake | `ACD-2500c-1 -> ACD-2500c-3 (expects_from)` at ACD-2500c-1.yaml:95; `ACD-2500c-3 -> ACD-2500c-1 (depends_on)` at ACD-2500c-3.yaml:27 |
  | 2 | BO-2400a-1-i / BO-2400f-3-ii / BO-2400f-5-iii | BO-2400a-1-i is done and sits outside most id sets | `BO-2400a-1-i -> BO-2400f-3-ii (expects_from)` at BO-2400a-1-i.yaml:329; `BO-2400f-3-ii -> BO-2400f-5-iii (depends_on)` at BO-2400f-3-ii.yaml:41; `BO-2400f-5-iii -> BO-2400a-1-i (depends_on)` at BO-2400f-5-iii.yaml:44 |
  | 3 | BO-2900a-1 / BO-2900a-2 | wrong-way sibling `depends_on` | `BO-2900a-1 -> BO-2900a-2 (expects_from)` at BO-2900a-1.yaml:82; `BO-2900a-2 -> BO-2900a-1 (depends_on)` at BO-2900a-2.yaml:30-32. BO-2900a-2's own `delivers_to` (:112) says "Consumed by BO-2900a-1", so a-2 is the producer and its `depends_on` is the likely spurious edge. |
  | 4 | BO-2900b-1 / BO-2900b-3 / BO-2900c-1 / BO-2900c-4 | three-field knot | `BO-2900b-1 -> BO-2900b-3 (expects_from)` at BO-2900b-1.yaml:78; `BO-2900b-3 -> BO-2900b-1 (depends_on)` at BO-2900b-3.yaml:29; `BO-2900b-3 -> BO-2900c-4 (expects_from)` at BO-2900b-3.yaml:66; `BO-2900c-1 -> BO-2900b-3 (expects_from)` at BO-2900c-1.yaml:75; `BO-2900c-4 -> BO-2900c-1 (depends_on)` at BO-2900c-4.yaml:32; `BO-2900c-4 -> BO-2900b-1 (expects_from)` at BO-2900c-4.yaml:73 |
  | 5 | BO-4300a-1 / BO-4300c-2 | `expects_from` in both directions | `BO-4300a-1 -> BO-4300c-2 (expects_from)` at BO-4300a-1.yaml:95; `BO-4300c-2 -> BO-4300a-1 (expects_from)` at BO-4300c-2.yaml:94 |
  | 6 | TQ-500g-1-vii / TQ-500g-1-viii | two-way handshake | `TQ-500g-1-vii -> TQ-500g-1-viii (expects_from)` at TQ-500g-1-vii.yaml:58; `TQ-500g-1-viii -> TQ-500g-1-vii` through both `depends_on` (:44) and `expects_from` (:75) of TQ-500g-1-viii.yaml |

- **The other 3 groups are not live.** No action is needed unless one of them is re-opened. Their
  members are found by re-running the replay.
- **"Live", as tested here:** a cyclic group with at least one member whose `work_status` is not
  `done`. By this definition the store at ed2190fd3 has one more live group than ticket 08's count:
  TQ-600a-2 / TQ-600a-5, where TQ-600a-2 is `todo`. That group closes through the prose-marked
  TQ-600a-5 entry below, so moving that entry, which the rulings require anyway, removes it.
- **User rulings (2026-10-07).**
  - `expects_from` always means build order. A relation-only link goes elsewhere. The store already
    uses `doc_links` for this ("which is why this is a doc_link and not a depends_on edge",
    ACD-2200.yaml:69; BP-1600a-2.yaml:89).
  - The 4 `expects_from` entries whose prose says they are not build-order edges are fixed in the store:
    - ACD-1900b-5-i.yaml:100-101 -> ACD-1900b-1: "NOT a blocking prerequisite";
    - BP-1500d-1.yaml:119-120 -> BP-900h-1: "DELIBERATELY NOT A depends_on";
    - BP-1500d-3.yaml:112-113 -> BP-900h-1: "Still deliberately NOT a depends_on";
    - TQ-600a-5.yaml:140-142 -> TQ-600a-2: "NOT A BUILD-ORDER EDGE".
  - Blocking generation until the data is fixed is accepted.
- **Recorded remediation.** KI-ACD-20260929
  (`docs/known-issues/ac-driven-dev/open-high-ki-acd-20260929-cross-field-dependency-cycle-is-invisible-to-both-tools.md`,
  Workaround): "decide which edge is spurious and delete it in the store, do not let the generator
  choose". Precedent: commit 92923a26 dropped TQ-600a-5's `depends_on` edge.
- **AC edits need a business-analyst pass and the user's approval.** Several records are approved,
  and six are `done`: BO-2400a-1-i, BO-2900b-1 and the four prose-marked records.

## Acceptance Criteria
- [ ] AC-1: For each of the 6 live groups, the business-analyst names the spurious edge and the user approves it before it is deleted. Each edited record gets an `amended_by` entry naming this ticket, dec-46476988badbd5e6, the deleted edge and the approval date.
- [ ] AC-2: None of the 4 prose-marked entries is in `expects_from` any more. Where the relationship is still worth keeping, it is a `doc_links` entry that carries the prose. No `expects_from` entry anywhere in the store says it is not a build-order edge.
- [ ] AC-3: A replay of ticket 08's merged ordering rule over the whole store finds 0 live cyclic groups. The rule is `depends_on` plus `expects_from`, with the parent-link yield. The 3 non-live groups may remain.
- [ ] AC-4: For each of the 6 former groups, `python scripts/goal_to_epic.py --ids <members> --dry-run` exits 0 and prints a build order, with no cycle error.
- [ ] AC-5: The commit that stages the edited records passes the pre-commit hooks without `SKIP`. If a `done` record cannot pass check-done-proof (see Risk & Safety), the user's decision for it is recorded in its `amended_by` entry.

## Test Requirements

```yaml
tests:
  - name: test_store_ordering_graph_has_no_live_cycle
    location: unit_tests/ac_store/test_ac_store_ordering_graph_has_no_live_cycle.py
    type: integration
    covers: [AC-3]
    description: |
      Build the ordering graph over the real docs/acceptance-criteria store with ticket 08's own
      graph function (imported, not copied), find its strongly connected components, and assert
      that none has a member whose work_status is not done. On failure, print each group in
      ticket 08's one-line-per-edge format. Red before the data fix (7 groups by this definition
      at ed2190fd3), green after it.
  - name: test_no_expects_from_entry_disclaims_build_order
    location: unit_tests/ac_store/test_ac_store_ordering_graph_has_no_live_cycle.py
    type: integration
    covers: [AC-2]
    description: |
      Read every expects_from entry in the real store, in all its shapes. No entry's contract
      text says it is not a build-order edge (patterns at least: "not a build-order edge",
      "not a depends_on", "not a blocking prerequisite"). Red today on the 4 entries in Context.
  - name: test_each_former_group_dry_runs_without_a_cycle
    location: unit_tests/ac_store/test_ac_store_ordering_graph_has_no_live_cycle.py
    type: integration
    covers: [AC-4]
    description: |
      For each of the 6 groups, run `python scripts/goal_to_epic.py --ids <members> --dry-run` as a
      subprocess against the real store. Exit 0, and no cycle error in the output.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | (review of the amended_by entries) | | |
| AC-2 | test_no_expects_from_entry_disclaims_build_order | | |
| AC-3 | test_store_ordering_graph_has_no_live_cycle | | |
| AC-4 | test_each_former_group_dry_runs_without_a_cycle | | |
| AC-5 | (the commit itself) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

Drive order: test-writer, then the business-analyst pass, then the rest. `build-feature.js` has no
`business-analyst` entry in `phaseOrder`, and an unknown agent sorts last, after commit and
pull-request (`templates/workflows-js/build-feature.js:457-475`). So run the business-analyst pass by
hand (`/ba`) at its place in the order.

### test-writer
- [ ] Write `unit_tests/ac_store/test_ac_store_ordering_graph_has_no_live_cycle.py`. It must be red
  before the business-analyst's edits.

### business-analyst (needs the user's approval for each edit)
- [ ] For each of the 6 groups, read both fields of every member and propose the spurious edge, with
  the reason. Delete only the edges the user approves.
- [ ] Move the 4 prose-marked entries out of `expects_from`, to `doc_links` where the relationship is
  worth keeping.
- [ ] Add the `amended_by` entries (AC-1).
- [ ] Before staging, run check-done-proof over every edited `done` record (BO-2400a-1-i, BO-2900b-1,
  ACD-1900b-5-i, BP-1500d-1, BP-1500d-3, TQ-600a-5).

### test-runner / pr-reviewer / commit
- [ ] Run the new file and ticket 08's tests (`unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py`,
  `unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py`).

## Risk & Safety
- Touches money? No.
- Touches data? Yes, AC store edges. This changes the build order of every epic generated from these
  trees later. Existing epics are not rewritten.
- **BP-1500d-1 cannot be staged as it is today.** It is a `done` composite whose children BP-1500d-1-i
  and BP-1500d-1-ii are unproven. `check_staged_done_proofs` refuses it (run 2026-10-07), and the
  required proof-of-done CI check reads the same rule. Editing it needs a decision first: reopen it to
  `in_progress` (BO-202's rule), or prove the children. The other 5 `done` records pass that check
  today.
- Reversibility: revert the commit.

## Out of Scope
- Any code change to the ordering rule or the cycle error. That is ticket 08.
- The 3 non-live groups, unless one is re-opened.
- Teaching `check_ac_circular_deps.py` to read `expects_from` (KI-ACD-20260929, remediation 1):
  `TICKET-20261007-CircularDepsGateReadsExpectsFrom`, which can be switched on only after this ticket lands.
- `expects_from` written as a bare id string or a list of id strings
  (`TICKET-20261007-ExpectsFromStringShapesAreEdges`). Counting those edges adds no cycle at
  ed2190fd3.
