---
epic_name: EPIC-DefineABehaviorOnce,ReuseTheSpec
created: 2026-06-11
status: done
components:
  - ac_store
source_ac: ACS-500
---
# EPIC-DefineABehaviorOnce,ReuseTheSpec

## Goal

This epic implements AC ACS-500: Define a behavior once, reuse the spec everywhere it appears. It consists of 17 ticket(s) generated from the leaf ACs beneath ACS-500, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260611-ACS-500a-1.md](./01_TICKET-20260611-ACS-500a-1.md) | A pattern AC defines shared behavior with parameterized slots | ACS-500a-1 | ACS-500a |
| 02 | [02_TICKET-20260611-ACS-500a-2.md](./02_TICKET-20260611-ACS-500a-2.md) | Pattern definitions live in the existing component registry hierarchy | ACS-500a-2 | ACS-500a |
| 03 | [03_TICKET-20260611-ACS-500a-3.md](./03_TICKET-20260611-ACS-500a-3.md) | Schema validates implements_pattern references point to existing ACs | ACS-500a-3 | ACS-500a, ACS-500a-1 |
| 04 | [04_TICKET-20260611-ACS-500a-3-i.md](./04_TICKET-20260611-ACS-500a-3-i.md) | pattern_bindings with missing keys are rejected at commit time | ACS-500a-3-i | ACS-500a-3 |
| 05 | [05_TICKET-20260611-ACS-500a-3-ii.md](./05_TICKET-20260611-ACS-500a-3-ii.md) | implements_pattern referencing a deprecated pattern is rejected | ACS-500a-3-ii | ACS-500a-3 |
| 06 | [06_TICKET-20260611-ACS-500b-1.md](./06_TICKET-20260611-ACS-500b-1.md) | A consuming AC declares pattern reference and page-specific bindings | ACS-500b-1 | ACS-500b, ACS-500a-1 |
| 07 | [07_TICKET-20260611-ACS-500b-1-i.md](./07_TICKET-20260611-ACS-500b-1-i.md) | AC with implements_pattern but empty criteria is valid | ACS-500b-1-i | ACS-500b-1 |
| 08 | [08_TICKET-20260611-ACS-500b-2.md](./08_TICKET-20260611-ACS-500b-2.md) | Pattern deviations are separate page-specific ACs, not inline overrides | ACS-500b-2 | ACS-500b, ACS-500b-1 |
| 09 | [09_TICKET-20260611-ACS-500c-1.md](./09_TICKET-20260611-ACS-500c-1.md) | BA agent checks for existing pattern before writing new behavioral AC | ACS-500c-1 | ACS-500c, ACS-500a-1 |
| 10 | [10_TICKET-20260611-ACS-500c-2.md](./10_TICKET-20260611-ACS-500c-2.md) | IT PO agent preserves implements_pattern when enriching an AC | ACS-500c-2 | ACS-500c, ACS-500a-1 |
| 11 | [11_TICKET-20260611-ACS-500c-3.md](./11_TICKET-20260611-ACS-500c-3.md) | Duplicate detection rejects AC whose criteria duplicates an existing pattern | ACS-500c-3 | ACS-500c, ACS-500a-3 |
| 12 | [12_TICKET-20260611-ACS-500d-1.md](./12_TICKET-20260611-ACS-500d-1.md) | Updating a pattern AC's criteria changes effective behavior for all consumers | ACS-500d-1 | ACS-500d, ACS-500b-1 |
| 13 | [13_TICKET-20260611-ACS-500d-1-i.md](./13_TICKET-20260611-ACS-500d-1-i.md) | Deleting a pattern AC is blocked when consumers still reference it | ACS-500d-1-i | ACS-500d-1 |
| 14 | [14_TICKET-20260611-ACS-500d-2.md](./14_TICKET-20260611-ACS-500d-2.md) | Existing page deviations survive pattern updates unchanged | ACS-500d-2 | ACS-500d, ACS-500b-2 |
| 15 | [15_TICKET-20260611-ACS-500e-1.md](./15_TICKET-20260611-ACS-500e-1.md) | Atomic pattern ACs compose into named composite pattern ACs | ACS-500e-1 | ACS-500e, ACS-500a-1 |
| 16 | [16_TICKET-20260611-ACS-500e-1-i.md](./16_TICKET-20260611-ACS-500e-1-i.md) | Circular composition dependency is detected and rejected | ACS-500e-1-i | ACS-500e-1 |
| 17 | [17_TICKET-20260611-ACS-500e-2.md](./17_TICKET-20260611-ACS-500e-2.md) | Composition depth is visible through the AC parent-child hierarchy | ACS-500e-2 | ACS-500e, ACS-500e-1 |

## Dependencies

```
ACS-500a-1 (no dependencies)
ACS-500a-2 (no dependencies)
ACS-500a-3 -> ACS-500a-1
ACS-500a-3-i -> ACS-500a-3
ACS-500a-3-ii -> ACS-500a-3
ACS-500b-1 -> ACS-500a-1
ACS-500b-1-i -> ACS-500b-1
ACS-500b-2 -> ACS-500b-1
ACS-500c-1 -> ACS-500a-1
ACS-500c-2 -> ACS-500a-1
ACS-500c-3 -> ACS-500a-3
ACS-500d-1 -> ACS-500b-1
ACS-500d-1-i -> ACS-500d-1
ACS-500d-2 -> ACS-500b-2
ACS-500e-1 -> ACS-500a-1
ACS-500e-1-i -> ACS-500e-1
ACS-500e-2 -> ACS-500e-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| llm-expert | 09, 10 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 17 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17 |

