---
epic_name: EPIC-EnforceFrontendPageDocs
created: 2026-06-17
status: in_progress
components:
  - commit_guardian
source_ac: GE-104
---
# EPIC-EnforceFrontendPageDocs

## Goal

This epic implements AC GE-104: New work never ships without the documentation it needs. It consists of 10 ticket(s) generated from the leaf ACs beneath GE-104, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260617-GE-104a-1.md](./01_TICKET-20260617-GE-104a-1.md) | Commit-time guardrail blocks a new frontend page that ships without its reference doc | GE-104a-1 | GE-104a |
| 02 | [02_TICKET-20260617-GE-104a-1-i.md](./02_TICKET-20260617-GE-104a-1-i.md) | Page-path to doc-path mapping is deterministic for a simple route segment | GE-104a-1-i | GE-104a-1 |
| 03 | [03_TICKET-20260617-GE-104a-1-ii.md](./03_TICKET-20260617-GE-104a-1-ii.md) | Nested and dynamic route segments derive a single deterministic doc path | GE-104a-1-ii | GE-104a-1 |
| 04 | [04_TICKET-20260617-GE-104a-1-iii.md](./04_TICKET-20260617-GE-104a-1-iii.md) | Deleting or renaming a page does not falsely block the commit | GE-104a-1-iii | GE-104a-1 |
| 05 | [05_TICKET-20260617-GE-104a-1-iv.md](./05_TICKET-20260617-GE-104a-1-iv.md) | Page-documentation hook is registered in commit_guardian.json with a hooks_manifest entry | GE-104a-1-iv | GE-104a-1 |
| 06 | [06_TICKET-20260617-GE-104a-2.md](./06_TICKET-20260617-GE-104a-2.md) | Planning-time trigger flips documentation-expert to needed when a ticket adds a new page without its reference doc | GE-104a-2 | GE-104a |
| 07 | [07_TICKET-20260617-GE-104a-2-i.md](./07_TICKET-20260617-GE-104a-2-i.md) | DSL trigger expresses a new-page-without-matching-doc condition (negation feasibility open question) | GE-104a-2-i | GE-104a-2 |
| 08 | [08_TICKET-20260617-GE-104a-3.md](./08_TICKET-20260617-GE-104a-3.md) | A how-to guide ships with the page-documentation guardrail so operators can configure and respond to it | GE-104a-3 | GE-104a, GE-104a-1, GE-104a-2 |
| 09 | [09_TICKET-20260617-GE-104a-4.md](./09_TICKET-20260617-GE-104a-4.md) | A sequence diagram documents the two-layer enforcement flow for new-page documentation | GE-104a-4 | GE-104a, GE-104a-1, GE-104a-2 |
| 10 | [10_TICKET-20260617-GE-104a-5.md](./10_TICKET-20260617-GE-104a-5.md) | The planning-time trigger genuinely enforces a new page's documentation rather than silently falling back to not_needed | GE-104a-5 | GE-104a, GE-104a-2, GE-104a-2-i |

## Dependencies

```
GE-104a-1 (no dependencies)
GE-104a-1-i -> GE-104a-1
GE-104a-1-ii -> GE-104a-1
GE-104a-1-iii -> GE-104a-1
GE-104a-1-iv -> GE-104a-1
GE-104a-2 (no dependencies)
GE-104a-2-i -> GE-104a-2
GE-104a-3 -> GE-104a-1, GE-104a-2
GE-104a-4 -> GE-104a-1, GE-104a-2
GE-104a-5 -> GE-104a-2, GE-104a-2-i
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 09 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| documentation-expert | 08 |
| llm-expert | 06, 07 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| pull-request | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| python-coder | 01, 02, 03, 04, 05, 10 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10 |

