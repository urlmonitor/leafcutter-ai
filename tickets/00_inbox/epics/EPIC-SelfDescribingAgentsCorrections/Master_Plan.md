---
epic_name: EPIC-AnAgentThatCannotDescribeItselfDoesNot
created: 2026-06-08
status: in_progress
components:
  - infrastructure
source_ac: INF-600g
---
# EPIC-AnAgentThatCannotDescribeItselfDoesNot

## Goal

This epic implements AC INF-600g: An agent that cannot describe itself does not pass the build. It consists of 5 ticket(s) generated from the leaf ACs beneath INF-600g, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260608-INF-600g-1.md](./01_TICKET-20260608-INF-600g-1.md) | Build validates that spawned_by entries are reciprocal with spawn_allowlist entries | INF-600g-1 | — |
| 02 | [02_TICKET-20260608-INF-600g-2.md](./02_TICKET-20260608-INF-600g-2.md) | Build detects phase agents redundantly listed alongside __ticket_phase_agents__ macro | INF-600g-2 | — |
| 03 | [03_TICKET-20260608-INF-600g-3.md](./03_TICKET-20260608-INF-600g-3.md) | Build cross-references skills_invoked against actual skill usage in agent template body | INF-600g-3 | — |
| 04 | [04_TICKET-20260608-INF-600g-2-i.md](./04_TICKET-20260608-INF-600g-2-i.md) | Non-phase agent individually listed alongside __ticket_phase_agents__ is valid | INF-600g-2-i | 02 (INF-600g-2) |
| 05 | [05_TICKET-20260608-INF-600g-3-i.md](./05_TICKET-20260608-INF-600g-3-i.md) | Project-local skill referenced in skills_invoked resolves via .claude/skills/ fallback | INF-600g-3-i | 03 (INF-600g-3) |

## Dependencies

```
INF-600g-1 (no dependencies)
INF-600g-2 (no dependencies)
INF-600g-3 (no dependencies)
INF-600g-2-i → depends on INF-600g-2 (ticket 02)
INF-600g-3-i → depends on INF-600g-3 (ticket 03)
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01, 02, 03, 04, 05 |
| pr-reviewer | 01, 02, 03, 04, 05 |
| pull-request | 01, 02, 03, 04, 05 |
| python-coder | 01, 02, 03, 04, 05 |
| test-runner | 01, 02, 03, 04, 05 |
| test-writer | 01, 02, 03, 04, 05 |
