---
epic_name: EPIC-CompleteComponentCoverageInTheRegistry
created: 2026-06-08
status: done
components:
  - ac-store
source_ac: ACS-300g
---
# EPIC-CompleteComponentCoverageInTheRegistry

## Goal

This epic implements AC ACS-300g: Complete component coverage in the registry. It consists of 5 ticket(s) generated from the leaf ACs beneath ACS-300g, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260608-ACS-300g-1.md](./01_TICKET-20260608-ACS-300g-1.md) | Each backfilled component entry satisfies the minimum schema | ACS-300g-1 | — |
| 02 | [02_TICKET-20260608-ACS-300g-2.md](./02_TICKET-20260608-ACS-300g-2.md) | Existing component entries are preserved unmodified during backfill | ACS-300g-2 | — |
| 03 | [03_TICKET-20260608-ACS-300g-3.md](./03_TICKET-20260608-ACS-300g-3.md) | Every agent-backed subsystem has a corresponding component entry | ACS-300g-3 | ACS-300g-1 |
| 04 | [04_TICKET-20260608-ACS-300g-4a.md](./04_TICKET-20260608-ACS-300g-4a.md) | Write tooling Python script for adding component entries to the registry | ACS-300g-4a | ACS-300g-1 |
| 05 | [05_TICKET-20260608-ACS-300g-4b.md](./05_TICKET-20260608-ACS-300g-4b.md) | Skill wrapper for the add-component script | ACS-300g-4b | ACS-300g-1, ACS-300g-4a |

## Dependencies

```
ACS-300g-1 (no dependencies)
ACS-300g-2 (no dependencies)
ACS-300g-3 -> ACS-300g-1
ACS-300g-4a -> ACS-300g-1
ACS-300g-4b -> ACS-300g-1, ACS-300g-4a
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05 |
| llm-expert | 05 |
| pr-reviewer | 01, 02, 03, 04, 05 |
| pull-request | 01, 02, 03, 04, 05 |
| python-coder | 01, 02, 03, 04 |
| test-runner | 01, 02, 03, 04, 05 |
| test-writer | 01, 02, 03, 04, 05 |

