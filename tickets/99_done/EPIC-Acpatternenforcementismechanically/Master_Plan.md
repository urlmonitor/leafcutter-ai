---
epic_name: EPIC-AcPatternEnforcementIsMechanically
created: 2026-06-17
status: in_progress
components:
  - ac-store
source_ac: ACS-500f
---
# EPIC-AcPatternEnforcementIsMechanically

## Goal

This epic implements AC ACS-500f: AC pattern enforcement is mechanically guaranteed, not prompt-only. It consists of 5 ticket(s) generated from the leaf ACs beneath ACS-500f, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260617-ACS-500f-1.md](./01_TICKET-20260617-ACS-500f-1.md) | Binding-completeness and field-preservation checks fire at commit time | ACS-500f-1 | ACS-500f |
| 02 | [02_TICKET-20260617-ACS-500f-1-i.md](./02_TICKET-20260617-ACS-500f-1-i.md) | Schema hook fails open and never blocks an unrelated commit on its own error | ACS-500f-1-i | ACS-500f-1 |
| 03 | [03_TICKET-20260617-ACS-500f-2.md](./03_TICKET-20260617-ACS-500f-2.md) | Pattern-first inventory recognizes a pattern AC by the same definition the hook uses | ACS-500f-2 | ACS-500f |
| 04 | [04_TICKET-20260617-ACS-500f-3.md](./04_TICKET-20260617-ACS-500f-3.md) | AC store schema accepts the real hierarchical id format and the pattern_slots field | ACS-500f-3 | ACS-500f |
| 05 | [05_TICKET-20260617-ACS-500f-3-i.md](./05_TICKET-20260617-ACS-500f-3-i.md) | Widened schema still rejects malformed ids and unknown fields | ACS-500f-3-i | ACS-500f-3 |

## Dependencies

```
ACS-500f-1 (no dependencies)
ACS-500f-1-i -> ACS-500f-1
ACS-500f-2 (no dependencies)
ACS-500f-3 (no dependencies)
ACS-500f-3-i -> ACS-500f-3
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05 |
| pr-reviewer | 01, 02, 03, 04, 05 |
| pull-request | 01, 02, 03, 04, 05 |
| python-coder | 01, 02, 04, 05 |
| test-runner | 01, 02, 03, 04, 05 |
| test-writer | 01, 02, 03, 04, 05 |
| workflow-architect | 03 |

