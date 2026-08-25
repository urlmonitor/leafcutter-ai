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
  - build_pipeline
  - commit_guardian
  - documentation_system
  - precommit_hooks
source_ac: GE-122d
---
# EPIC-TheNumberingGuaranteeHoldsAtEveryStage

## Goal

This epic implements AC GE-122d: The numbering guarantee holds at every stage and cannot be waved through. It consists of 9 ticket(s) generated from the leaf ACs beneath GE-122d, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260825-GE-122d-1.md](./01_TICKET-20260825-GE-122d-1.md) | One rule, evaluated at three stages, cannot give three different answers | GE-122d-1 | — |
| 02 | [02_TICKET-20260825-GE-122d-2.md](./02_TICKET-20260825-GE-122d-2.md) | A clash that slipped past the commit check is still stopped before it reaches everyone | GE-122d-2 | TICKET-20260825-GE-122d-1.md |
| 03 | [03_TICKET-20260825-GE-122d-3.md](./03_TICKET-20260825-GE-122d-3.md) | A pass that could not see the whole collection never reports success | GE-122d-3 | — |
| 04 | [04_TICKET-20260825-GE-122d-3-i.md](./04_TICKET-20260825-GE-122d-3-i.md) | A defect in the guard itself is announced but does not hold an unrelated commit hostage | GE-122d-3-i | — |
| 05 | [05_TICKET-20260825-GE-122d-3-ii.md](./05_TICKET-20260825-GE-122d-3-ii.md) | A new project's first commit works because the roots are there, not because absence is excused | GE-122d-3-ii | — |
| 06 | [06_TICKET-20260825-GE-122d-4.md](./06_TICKET-20260825-GE-122d-4.md) | The three-stage arrangement is drawn, showing which stage owns which promise | GE-122d-4 | TICKET-20260825-GE-122d-1.md, TICKET-20260825-GE-122d-2.md |
| 07 | [07_TICKET-20260825-GE-122d-5.md](./07_TICKET-20260825-GE-122d-5.md) | Which stage you can skip, and what still catches you, is written down | GE-122d-5 | TICKET-20260825-GE-122d-2.md, TICKET-20260825-GE-122d-3.md |
| 08 | [08_TICKET-20260825-GE-122d-6.md](./08_TICKET-20260825-GE-122d-6.md) | The commit-time numbering check is wired into the live registry and fires on a real commit | GE-122d-6 | TICKET-20260825-GE-122d-1.md, TICKET-20260825-GE-122d-3-ii.md |
| 09 | [09_TICKET-20260825-GE-122d-6-i.md](./09_TICKET-20260825-GE-122d-6-i.md) | A pass states what it inspected, so a pass is distinguishable from a hook that never ran | GE-122d-6-i | — |

## Dependencies

```
GE-122d-1 (no dependencies)
GE-122d-2 -> GE-122d-1
GE-122d-3 (no dependencies)
GE-122d-3-i -> GE-122d-3
GE-122d-3-ii -> GE-122d-3
GE-122d-4 -> GE-122d-1, GE-122d-2
GE-122d-5 -> GE-122d-2, GE-122d-3
GE-122d-6 -> GE-122d-1, GE-122d-3-ii
GE-122d-6-i -> GE-122d-6
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04, 05, 06, 08, 09 |
| ac-validator | 01, 02, 03, 04, 05, 06, 08, 09 |
| architect-review | 01, 02, 03, 04, 05, 08, 09 |
| architecture-diagram-author | 06 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| documentation-expert | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| documentation-verifier | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| pr-reviewer | 01, 02, 03, 04, 05, 08, 09 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| python-coder | 01, 02, 03, 04, 05, 08, 09 |
| test-runner | 01, 02, 03, 04, 05, 08, 09 |
| test-writer | 01, 02, 03, 04, 05, 08, 09 |
| user-surface-smoker | 08 |

