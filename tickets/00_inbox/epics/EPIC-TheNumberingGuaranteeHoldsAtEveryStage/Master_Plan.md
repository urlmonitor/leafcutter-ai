---
title: "EPIC-TheNumberingGuaranteeHoldsAtEveryStage — the numbering guarantee holds at every stage and cannot be waved through"
epic_name: EPIC-TheNumberingGuaranteeHoldsAtEveryStage
created: 2026-08-25
status: in_progress
type: epic
depends_on: []
requires_diagram: false
requires_adr: false
change_target:
  - code
  - pipeline
risk_surface: contract_boundary
components:
  - ac_store
  - build_pipeline
  - commit_guardian
  - documentation_system
  - precommit_hooks
  - ticket_lifecycle
source_ac: GE-122d
---
# EPIC-TheNumberingGuaranteeHoldsAtEveryStage

## Goal

This epic implements AC GE-122d: The numbering guarantee holds at every stage and cannot be waved through. It consists of 12 tickets in topological build order — nine generated from the leaf ACs beneath GE-122d, plus three added by hand for prerequisites that live under other L1 parents (see below). All inter-ticket dependencies are derived from the AC `depends_on` graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260825-GE-122d-1.md](./01_TICKET-20260825-GE-122d-1.md) | One rule, evaluated at three stages, cannot give three different answers | GE-122d-1 | — |
| 02 | [02_TICKET-20260825-GE-122d-2.md](./02_TICKET-20260825-GE-122d-2.md) | A clash that slipped past the commit check is still stopped before it reaches everyone | GE-122d-2 | 01 |
| 03 | [03_TICKET-20260825-GE-122d-3.md](./03_TICKET-20260825-GE-122d-3.md) | A pass that could not see the whole collection never reports success | GE-122d-3 | — |
| 04 | [04_TICKET-20260825-GE-122d-3-i.md](./04_TICKET-20260825-GE-122d-3-i.md) | A defect in the guard itself is announced but does not hold an unrelated commit hostage | GE-122d-3-i | 03 |
| 05 | [05_TICKET-20260825-GE-122d-3-ii.md](./05_TICKET-20260825-GE-122d-3-ii.md) | A new project's first commit works because the roots are there, not because absence is excused | GE-122d-3-ii | 03 |
| 06 | [06_TICKET-20260825-GE-122d-4.md](./06_TICKET-20260825-GE-122d-4.md) | The three-stage arrangement is drawn, showing which stage owns which promise | GE-122d-4 | 01, 02 |
| 07 | [07_TICKET-20260825-GE-122d-5.md](./07_TICKET-20260825-GE-122d-5.md) | Which stage you can skip, and what still catches you, is written down | GE-122d-5 | 02, 03 |
| 08 | [08_TICKET-20260825-GE-122e-2.md](./08_TICKET-20260825-GE-122e-2.md) | Each work item that exists twice is reduced to the one copy that is right | GE-122e-2 | — |
| 09 | [09_TICKET-20260825-GE-122e-3.md](./09_TICKET-20260825-GE-122e-3.md) | The repaired collection passes the guard itself, with nothing excused | GE-122e-3 | 08, `../../../99_done/TICKET-20260817-GE-122e-1.md` (done) |
| 10 | [10_TICKET-20260825-BP-900h-6.md](./10_TICKET-20260825-BP-900h-6.md) | The simulation uses the install, not just builds it — a first commit is attempted | BP-900h-6 | `../EPIC-DeploymentCompleteness/12_TICKET-20260817-BP-900h-1.md` (**done**) |
| 11 | [11_TICKET-20260825-GE-122d-6.md](./11_TICKET-20260825-GE-122d-6.md) | The commit-time numbering check is wired into the live registry and fires on a real commit | GE-122d-6 | 01, 05, 09, 10 |
| 12 | [12_TICKET-20260825-GE-122d-6-i.md](./12_TICKET-20260825-GE-122d-6-i.md) | A pass states what it inspected, so a pass is distinguishable from a hook that never ran | GE-122d-6-i | 11 |

### Tickets 08–10 were added by hand after generation

`goal_to_epic.py --ac GE-122d` generates only the leaves beneath `GE-122d`. Three of
`GE-122d-6`'s declared prerequisites live under other L1 parents, so the generated epic
could not be driven to completion — ticket 11 would have halted with no ticket to wait for.
They were generated individually with `generate_ticket_from_ac.py` and inserted here:

- **08 `GE-122e-2`** and **09 `GE-122e-3`** (under `GE-122e`) — the duplicate work-item
  repair and its verification. `main` currently fails its own uniqueness pass on five
  twice-held work items, so registering the commit-time check before this repair lands
  would block every commit in this repository.
- **10 `BP-900h-6`** (under `BP-900h`) — the consumer-install commit job, the only surface
  that can observe a fresh-install regression caused by the registration.

**Ticket 10's external prerequisite is now met.** `BP-900h-6` adds a step *inside* the
consumer-simulation job that `BP-900h-1` creates. That job did not exist when this epic was
generated; it does now — `consumer-install-sim` in `.github/workflows/ci.yml`, backed by
`scripts/ci/check_consumer_install.py`, merged to `main` on 2026-08-26. `BP-900h-1`'s ticket
is `status: done`. Every ticket in this epic is therefore unblocked at the graph level.

The earlier note here read "tickets 01–09 and 12 are unaffected", which was wrong even at the
time: 12 depends on 11, and 11 depended on 10, so 12 was transitively gated too. Recorded
because a dependency claim that is checked by eye rather than by walking the graph is exactly
what this epic exists to make impossible.

## Dependencies

```
GE-122d-1    (no dependencies)
GE-122d-2    -> GE-122d-1
GE-122d-3    (no dependencies)
GE-122d-3-i  -> GE-122d-3
GE-122d-3-ii -> GE-122d-3
GE-122d-4    -> GE-122d-1, GE-122d-2
GE-122d-5    -> GE-122d-2, GE-122d-3
GE-122e-2    (no dependencies)
GE-122e-3    -> GE-122e-2, GE-122e-1 (already done)
BP-900h-6    -> BP-900h-1 (done — outside this epic)
GE-122d-6    -> GE-122d-1, GE-122d-3-ii, GE-122e-3, BP-900h-6
GE-122d-6-i  -> GE-122d-6
```

Every edge above is mirrored in the corresponding ticket's `depends_on` frontmatter, which
is what `build-feature` reads. The two were **not** in agreement as generated: the generator
rendered this block correctly but wrote `depends_on: []` into the frontmatter of every
ticket whose only dependency is its own parent AC — `GE-122d-3-i`, `GE-122d-3-ii` and
`GE-122d-6-i`. Sibling edges were written correctly, so the table looked right while three
tickets were machine-readable as unblocked. Repaired by hand; recorded as `KI-ACD-021`.

**Build order is load-bearing in this epic, not advisory.** `GE-122d-3-ii` scaffolds the
namespace roots and `GE-122d-6` registers the commit-time check against them. Registering
before scaffolding makes every commit in every fresh install fail closed on an unresolvable
root. That ordering exists only in `depends_on`.

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04, 05, 06, 08, 09, 10, 11, 12 |
| ac-validator | 01, 02, 03, 04, 05, 06, 08, 09, 10, 11, 12 |
| architect-review | 01, 02, 03, 04, 05, 10, 11, 12 |
| architecture-diagram-author | 06 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12 |
| documentation-expert | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12 |
| documentation-verifier | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12 |
| pr-reviewer | 01, 02, 03, 04, 05, 10, 11, 12 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12 |
| python-coder | 01, 02, 03, 04, 05, 08, 09, 10, 11, 12 |
| test-runner | 01, 02, 03, 04, 05, 08, 09, 10, 11, 12 |
| test-writer | 01, 02, 03, 04, 05, 08, 09, 10, 11, 12 |
| user-surface-smoker | 11 |

