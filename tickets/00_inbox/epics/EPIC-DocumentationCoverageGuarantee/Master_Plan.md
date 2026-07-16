---
epic_name: EPIC-DocumentationCoverageGuarantee
title: "EPIC: Documentation Coverage Guarantee"
type: epic
created: 2026-07-15
status: todo
components:
  - build_orchestration
source_ac: BO-2200
depends_on: []
requires_diagram: false
requires_adr: true
change_target: pipeline
risk_surface: contract_boundary
---
# EPIC-DocumentationCoverageGuarantee

## Goal

This epic implements AC BO-2200: Documentation stays correct and complete, automatically. It consists of 29 ticket(s) generated from the leaf ACs beneath BO-2200, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260715-BO-2200a-1.md](./01_TICKET-20260715-BO-2200a-1.md) | A declarative documentation-gates policy demands docs for user-facing, data, flow, and docs changes | BO-2200a-1 | BO-2200a |
| 02 | [02_TICKET-20260715-BO-2200a-2.md](./02_TICKET-20260715-BO-2200a-2.md) | A boundary, safety, auth, or privacy risk surface also demands documentation | BO-2200a-2 | BO-2200a, BO-2200a-1 |
| 03 | [03_TICKET-20260715-BO-2200a-3.md](./03_TICKET-20260715-BO-2200a-3.md) | A purely internal refactor does not demand documentation | BO-2200a-3 | BO-2200a, BO-2200a-1 |
| 04 | [04_TICKET-20260715-BO-2200a-3-i.md](./04_TICKET-20260715-BO-2200a-3-i.md) | A cost risk surface and an unclassified AC do not demand documentation | BO-2200a-3-i | BO-2200a-3 |
| 05 | [05_TICKET-20260715-BO-2200a-4.md](./05_TICKET-20260715-BO-2200a-4.md) | A list-valued change target triggers documentation if any element triggers (union semantics) | BO-2200a-4 | BO-2200a, BO-2200a-1 |
| 06 | [06_TICKET-20260715-BO-2200a-5.md](./06_TICKET-20260715-BO-2200a-5.md) | The schema validator rejects documentation_triggers on any AC that is not level L1 | BO-2200a-5 | BO-2200a |
| 07 | [07_TICKET-20260715-BO-2200a-5-i.md](./07_TICKET-20260715-BO-2200a-5-i.md) | A valid documentation_triggers enum value on a non-L1 AC is still rejected for being off-level | BO-2200a-5-i | BO-2200a-5 |
| 08 | [08_TICKET-20260715-BO-2200b-1.md](./08_TICKET-20260715-BO-2200b-1.md) | A documentation-verifier phase runs after writing and before commit | BO-2200b-1 | BO-2200b |
| 09 | [09_TICKET-20260715-BO-2200b-2.md](./09_TICKET-20260715-BO-2200b-2.md) | The verifier fails the ticket when a required documentation file was not changed | BO-2200b-2 | BO-2200b, BO-2200b-1 |
| 10 | [10_TICKET-20260715-BO-2200b-2-i.md](./10_TICKET-20260715-BO-2200b-2-i.md) | Partial documentation coverage still fails, naming the specific missing doc | BO-2200b-2-i | BO-2200b-2 |
| 11 | [11_TICKET-20260715-BO-2200b-3.md](./11_TICKET-20260715-BO-2200b-3.md) | The verifier fails placeholder documentation and passes real content | BO-2200b-3 | BO-2200b, BO-2200b-1 |
| 12 | [12_TICKET-20260715-BO-2200b-3-i.md](./12_TICKET-20260715-BO-2200b-3-i.md) | A short but genuine doc passes while a heading-only or token-filled stub fails | BO-2200b-3-i | BO-2200b-3 |
| 13 | [13_TICKET-20260715-BO-2200b-4.md](./13_TICKET-20260715-BO-2200b-4.md) | Generating a ticket from a doc-triggering AC injects both the writer and the verifier | BO-2200b-4 | BO-2200b, BO-2200a-1 |
| 14 | [14_TICKET-20260715-BO-2200b-5.md](./14_TICKET-20260715-BO-2200b-5.md) | Once triggered, the writer and verifier cannot be suppressed by a not_needed override | BO-2200b-5 | BO-2200b, BO-2200b-4 |
| 15 | [15_TICKET-20260715-BO-2200b-5-i.md](./15_TICKET-20260715-BO-2200b-5-i.md) | A hand-edited not_needed on the verifier is restored to needed at generation time | BO-2200b-5-i | BO-2200b-5 |
| 16 | [16_TICKET-20260715-BO-2200b-6.md](./16_TICKET-20260715-BO-2200b-6.md) | The verifier is registered in every canonical phase-order source so it never sorts to the end | BO-2200b-6 | BO-2200b, BO-2200b-1 |
| 17 | [17_TICKET-20260715-BO-2200c-1.md](./17_TICKET-20260715-BO-2200c-1.md) | The generated ticket carries an Agent Contracts documentation-expert section in a fixed position | BO-2200c-1 | BO-2200c |
| 18 | [18_TICKET-20260715-BO-2200c-2.md](./18_TICKET-20260715-BO-2200c-2.md) | Each contract line names a genre, a target doc path, and a content constraint | BO-2200c-2 | BO-2200c, BO-2200c-1 |
| 19 | [19_TICKET-20260715-BO-2200c-3.md](./19_TICKET-20260715-BO-2200c-3.md) | The genre is sourced from the parent L1's documentation_triggers | BO-2200c-3 | BO-2200c, BO-2200c-2 |
| 20 | [20_TICKET-20260715-BO-2200c-3-i.md](./20_TICKET-20260715-BO-2200c-3-i.md) | An unresolved or absent parent L1 yields a genre-less contract line, not a crash | BO-2200c-3-i | BO-2200c-3 |
| 21 | [21_TICKET-20260715-BO-2200c-4.md](./21_TICKET-20260715-BO-2200c-4.md) | doc_links richness is surfaced as existing docs to update or cross-link | BO-2200c-4 | BO-2200c, BO-2200c-1 |
| 22 | [22_TICKET-20260715-BO-2200c-4-i.md](./22_TICKET-20260715-BO-2200c-4-i.md) | A doc_link that is a bare path or is missing optional fields is surfaced gracefully | BO-2200c-4-i | BO-2200c-4 |
| 23 | [23_TICKET-20260715-BO-2200c-5.md](./23_TICKET-20260715-BO-2200c-5.md) | The Agent Contracts block is the single source both the writer reads and the verifier asserts | BO-2200c-5 | BO-2200c, BO-2200c-1 |
| 24 | [24_TICKET-20260715-BO-2200c-6.md](./24_TICKET-20260715-BO-2200c-6.md) | A reference doc explains the documentation-coverage gate, the verifier, and the Agent Contracts brief | BO-2200c-6 | BO-2200c, BO-2200a-1, BO-2200b-1, BO-2200b-4, BO-2200c-1 |
| 25 | [25_TICKET-20260715-BO-2200d-1.md](./25_TICKET-20260715-BO-2200d-1.md) | documentation-expert is added via the post-coder surface path, not the pre-coder flow-change slot | BO-2200d-1 | BO-2200d, BO-2200a-1 |
| 26 | [26_TICKET-20260715-BO-2200d-1-i.md](./26_TICKET-20260715-BO-2200d-1-i.md) | Removing documentation-expert from the flow-change gates leaves the other pre-coder gates intact | BO-2200d-1-i | BO-2200d-1 |
| 27 | [27_TICKET-20260715-BO-2200d-2.md](./27_TICKET-20260715-BO-2200d-2.md) | On a doc-required ticket, the writer runs after code and tests and the verifier runs last before commit | BO-2200d-2 | BO-2200d, BO-2200d-1, BO-2200b-1 |
| 28 | [28_TICKET-20260715-BO-2200d-2-i.md](./28_TICKET-20260715-BO-2200d-2-i.md) | With multiple coders, documentation-expert is ordered after the last coder | BO-2200d-2-i | BO-2200d-2 |
| 29 | [29_TICKET-20260715-BO-2200d-3.md](./29_TICKET-20260715-BO-2200d-3.md) | A sequence diagram shows the doc-required ticket phase flow through writer and verifier to commit | BO-2200d-3 | BO-2200d, BO-2200d-2, BO-2200b-1 |

## Dependencies

```
BO-2200a-1 (no dependencies)
BO-2200a-2 -> BO-2200a-1
BO-2200a-3 -> BO-2200a-1
BO-2200a-3-i -> BO-2200a-3
BO-2200a-4 -> BO-2200a-1
BO-2200a-5 (no dependencies)
BO-2200a-5-i -> BO-2200a-5
BO-2200b-1 (no dependencies)
BO-2200b-2 -> BO-2200b-1
BO-2200b-2-i -> BO-2200b-2
BO-2200b-3 -> BO-2200b-1
BO-2200b-3-i -> BO-2200b-3
BO-2200b-4 -> BO-2200a-1
BO-2200b-5 -> BO-2200b-4
BO-2200b-5-i -> BO-2200b-5
BO-2200b-6 -> BO-2200b-1
BO-2200c-1 (no dependencies)
BO-2200c-2 -> BO-2200c-1
BO-2200c-3 -> BO-2200c-2
BO-2200c-3-i -> BO-2200c-3
BO-2200c-4 -> BO-2200c-1
BO-2200c-4-i -> BO-2200c-4
BO-2200c-5 -> BO-2200c-1
BO-2200c-6 -> BO-2200a-1, BO-2200b-1, BO-2200b-4, BO-2200c-1
BO-2200d-1 -> BO-2200a-1
BO-2200d-1-i -> BO-2200d-1
BO-2200d-2 -> BO-2200d-1, BO-2200b-1
BO-2200d-2-i -> BO-2200d-2
BO-2200d-3 -> BO-2200d-2, BO-2200b-1
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 29 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29 |
| documentation-expert | 24 |
| llm-expert | 09, 10, 11, 12, 16 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29 |

