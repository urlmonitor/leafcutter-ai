---
epic_name: EPIC-ACCodeTraceabilityGraph
created: 2026-06-22
status: in_progress
components:
  - knowledge_system
source_ac: KM-KGS-100
---
# EPIC-ACCodeTraceabilityGraph

## Goal

This epic implements AC KM-KGS-100: Trace any requirement to the exact code and tests that fulfil it. It consists of 15 ticket(s) generated from the leaf ACs beneath KM-KGS-100, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260622-KM-KGS-100a-1.md](./01_TICKET-20260622-KM-KGS-100a-1.md) | The acceptance-criteria store is a declared surface in the surfaces config | KM-KGS-100a-1 | KM-KGS-100a |
| 02 | [02_TICKET-20260622-KM-KGS-100a-2.md](./02_TICKET-20260622-KM-KGS-100a-2.md) | Each acceptance-criterion file becomes one node in the knowledge map | KM-KGS-100a-2 | KM-KGS-100a, KM-KGS-100a-1 |
| 03 | [03_TICKET-20260622-KM-KGS-100a-2-i.md](./03_TICKET-20260622-KM-KGS-100a-2-i.md) | Non-criterion and unparseable files under the acs surface produce no spurious nodes | KM-KGS-100a-2-i | KM-KGS-100a-2 |
| 04 | [04_TICKET-20260622-KM-KGS-100a-3.md](./04_TICKET-20260622-KM-KGS-100a-3.md) | An acceptance criterion's four relationship fields each become a distinct edge | KM-KGS-100a-3 | KM-KGS-100a, KM-KGS-100a-2 |
| 05 | [05_TICKET-20260622-KM-KGS-100a-4.md](./05_TICKET-20260622-KM-KGS-100a-4.md) | Component diagram shows the acceptance-criteria store as a knowledge-map surface | KM-KGS-100a-4 | KM-KGS-100a, KM-KGS-100a-3 |
| 06 | [06_TICKET-20260622-KM-KGS-100b-1.md](./06_TICKET-20260622-KM-KGS-100b-1.md) | Answer which code file delivers an acceptance criterion by following its edges | KM-KGS-100b-1 | KM-KGS-100b, KM-KGS-100a-3 |
| 07 | [07_TICKET-20260622-KM-KGS-100b-2.md](./07_TICKET-20260622-KM-KGS-100b-2.md) | Acceptance criteria and their links are visible in the knowledge-graph visualization | KM-KGS-100b-2 | KM-KGS-100b, KM-KGS-100b-1 |
| 08 | [08_TICKET-20260622-KM-KGS-100b-3.md](./08_TICKET-20260622-KM-KGS-100b-3.md) | How-to guide for tracing a requirement to its code and tests | KM-KGS-100b-3 | KM-KGS-100b, KM-KGS-100b-1 |
| 09 | [09_TICKET-20260622-KM-KGS-100b-4.md](./09_TICKET-20260622-KM-KGS-100b-4.md) | Sequence diagram of a requirement-to-code traversal | KM-KGS-100b-4 | KM-KGS-100b, KM-KGS-100b-1 |
| 10 | [10_TICKET-20260622-KM-KGS-100c-1.md](./10_TICKET-20260622-KM-KGS-100c-1.md) | Every surface declared in the config is ingested, however many there are | KM-KGS-100c-1 | KM-KGS-100c |
| 11 | [11_TICKET-20260622-KM-KGS-100c-2.md](./11_TICKET-20260622-KM-KGS-100c-2.md) | Declaring a new surface makes it join the map with no code change | KM-KGS-100c-2 | KM-KGS-100c, KM-KGS-100c-1 |
| 12 | [12_TICKET-20260622-KM-KGS-100c-3.md](./12_TICKET-20260622-KM-KGS-100c-3.md) | How-to guide for declaring a new knowledge surface | KM-KGS-100c-3 | KM-KGS-100c, KM-KGS-100c-2 |
| 13 | [13_TICKET-20260622-KM-KGS-100d-1.md](./13_TICKET-20260622-KM-KGS-100d-1.md) | Each declared surface is validated for the relationship kinds it promises | KM-KGS-100d-1 | KM-KGS-100d |
| 14 | [14_TICKET-20260622-KM-KGS-100d-2.md](./14_TICKET-20260622-KM-KGS-100d-2.md) | Every edge points to a node that actually exists | KM-KGS-100d-2 | KM-KGS-100d, KM-KGS-100d-1 |
| 15 | [15_TICKET-20260622-KM-KGS-100d-2-i.md](./15_TICKET-20260622-KM-KGS-100d-2-i.md) | A relationship pointing at a missing target is dropped, not rendered as a dead end | KM-KGS-100d-2-i | KM-KGS-100d-2 |

## Dependencies

```
KM-KGS-100a-1 (no dependencies)
KM-KGS-100a-2 -> KM-KGS-100a-1
KM-KGS-100a-2-i -> KM-KGS-100a-2
KM-KGS-100a-3 -> KM-KGS-100a-2
KM-KGS-100a-4 -> KM-KGS-100a-3
KM-KGS-100b-1 -> KM-KGS-100a-3
KM-KGS-100b-2 -> KM-KGS-100b-1
KM-KGS-100b-3 -> KM-KGS-100b-1
KM-KGS-100b-4 -> KM-KGS-100b-1
KM-KGS-100c-1 (no dependencies)
KM-KGS-100c-2 -> KM-KGS-100c-1
KM-KGS-100c-3 -> KM-KGS-100c-2
KM-KGS-100d-1 (no dependencies)
KM-KGS-100d-2 -> KM-KGS-100d-1
KM-KGS-100d-2-i -> KM-KGS-100d-2
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 05, 09 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15 |
| documentation-expert | 08, 12 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15 |
| python-coder | 01, 02, 03, 04, 06, 07, 10, 11, 13, 14, 15 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15 |

