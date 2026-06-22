---
epic_name: EPIC-IndependentSpotCheck
created: 2026-06-18
status: in_progress
components:
  - build-orchestration
source_ac: BO-1300
---
# EPIC-IndependentSpotCheck

## Goal

This epic implements AC BO-1300: Catch the problems your tests never thought to check before calling a feature done. It consists of 16 ticket(s) generated from the leaf ACs beneath BO-1300, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260618-BO-1300a-1.md](./01_TICKET-20260618-BO-1300a-1.md) | On-demand spot-check command targets a named finished feature | BO-1300a-1 | BO-1300a |
| 02 | [02_TICKET-20260618-BO-1300a-1-i.md](./02_TICKET-20260618-BO-1300a-1-i.md) | Spot-check command with no resolvable target is rejected before dispatch | BO-1300a-1-i | BO-1300a-1 |
| 03 | [03_TICKET-20260618-BO-1300a-2.md](./03_TICKET-20260618-BO-1300a-2.md) | On-demand command dispatches exactly three spot-check reviewers in parallel | BO-1300a-2 | BO-1300a, BO-1300a-1 |
| 04 | [04_TICKET-20260618-BO-1300b-1.md](./04_TICKET-20260618-BO-1300b-1.md) | Each of the three reviewers is seeded with a distinct review angle | BO-1300b-1 | BO-1300b |
| 05 | [05_TICKET-20260618-BO-1300b-1-i.md](./05_TICKET-20260618-BO-1300b-1-i.md) | Two reviewers may not collapse onto the same angle | BO-1300b-1-i | BO-1300b-1 |
| 06 | [06_TICKET-20260618-BO-1300b-2.md](./06_TICKET-20260618-BO-1300b-2.md) | Findings from all three reviewers are aggregated into one consolidated result | BO-1300b-2 | BO-1300b, BO-1300b-1 |
| 07 | [07_TICKET-20260618-BO-1300c-1.md](./07_TICKET-20260618-BO-1300c-1.md) | Reviewers exercise the feature for uncovered gaps and never run the unit test suite | BO-1300c-1 | BO-1300c |
| 08 | [08_TICKET-20260618-BO-1300a-3.md](./08_TICKET-20260618-BO-1300a-3.md) | How-to guide: requesting an independent spot-check of a finished feature | BO-1300a-3 | BO-1300a, BO-1300a-2, BO-1300c-1 |
| 09 | [09_TICKET-20260618-BO-1300c-1-i.md](./09_TICKET-20260618-BO-1300c-1-i.md) | Reviewer tempted to fall back to running tests must refuse and exercise the feature instead | BO-1300c-1-i | BO-1300c-1 |
| 10 | [10_TICKET-20260618-BO-1300d-1.md](./10_TICKET-20260618-BO-1300d-1.md) | The same three-reviewer spot-check runs automatically as the closing step of a build | BO-1300d-1 | BO-1300d, BO-1300a-2, BO-1300b-1 |
| 11 | [11_TICKET-20260618-BO-1300d-1-i.md](./11_TICKET-20260618-BO-1300d-1-i.md) | Blocking spot-check findings are surfaced in the build's completion output | BO-1300d-1-i | BO-1300d-1 |
| 12 | [12_TICKET-20260618-BO-1300d-2.md](./12_TICKET-20260618-BO-1300d-2.md) | Sequence diagram: automatic end-of-build spot-check wiring | BO-1300d-2 | BO-1300d, BO-1300d-1, BO-1300d-1-i |
| 13 | [13_TICKET-20260618-BO-1300e-1.md](./13_TICKET-20260618-BO-1300e-1.md) | Each spot-check finding is written as a ticket into the inbox for the fix flow | BO-1300e-1 | BO-1300e, BO-1300b-2 |
| 14 | [14_TICKET-20260618-BO-1300a-4.md](./14_TICKET-20260618-BO-1300a-4.md) | Sequence diagram: on-demand spot-check pass from invocation to tracked tickets | BO-1300a-4 | BO-1300a, BO-1300a-2, BO-1300b-2, BO-1300e-1 |
| 15 | [15_TICKET-20260618-BO-1300e-1-i.md](./15_TICKET-20260618-BO-1300e-1-i.md) | A clean spot-check creates no tickets and signs off the feature | BO-1300e-1-i | BO-1300e-1 |
| 16 | [16_TICKET-20260618-BO-1300e-1-ii.md](./16_TICKET-20260618-BO-1300e-1-ii.md) | Duplicate findings across reviewers are deduplicated to one ticket per distinct issue | BO-1300e-1-ii | BO-1300e-1 |

## Dependencies

```
BO-1300a-1 (no dependencies)
BO-1300a-1-i -> BO-1300a-1
BO-1300a-2 -> BO-1300a-1
BO-1300a-3 -> BO-1300a-2, BO-1300c-1
BO-1300a-4 -> BO-1300a-2, BO-1300b-2, BO-1300e-1
BO-1300b-1 (no dependencies)
BO-1300b-1-i -> BO-1300b-1
BO-1300b-2 -> BO-1300b-1
BO-1300c-1 (no dependencies)
BO-1300c-1-i -> BO-1300c-1
BO-1300d-1 -> BO-1300a-2, BO-1300b-1
BO-1300d-1-i -> BO-1300d-1
BO-1300d-2 -> BO-1300d-1, BO-1300d-1-i
BO-1300e-1 -> BO-1300b-2
BO-1300e-1-i -> BO-1300e-1
BO-1300e-1-ii -> BO-1300e-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 12, 14 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| documentation-expert | 08 |
| llm-expert | 01, 02, 03, 04, 05, 06, 07, 09 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| python-coder | 10, 11, 13, 15, 16 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |

