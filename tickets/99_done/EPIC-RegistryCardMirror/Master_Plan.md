---
epic_name: EPIC-RegistryCardMirror
created: 2026-07-06
status: in_progress
components:
  - infrastructure
source_ac: INF-600l
---
# EPIC-RegistryCardMirror

## Goal

This epic implements AC INF-600l: An agent's card can never quietly disagree with how the system actually wires that agent. It consists of 5 ticket(s) generated from the leaf ACs beneath INF-600l, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260706-INF-600l-1.md](./01_TICKET-20260706-INF-600l-1.md) | The consistency check catches a wired relationship present on one side (card or registry) but not the other | INF-600l-1 | INF-600l |
| 02 | [02_TICKET-20260706-INF-600l-1-i.md](./02_TICKET-20260706-INF-600l-1-i.md) | When agent cards are absent, the mirror check no-ops instead of false-failing | INF-600l-1-i | INF-600l-1 |
| 03 | [03_TICKET-20260706-INF-600l-1-ii.md](./03_TICKET-20260706-INF-600l-1-ii.md) | When the agent registry is absent, the mirror check no-ops instead of false-failing | INF-600l-1-ii | INF-600l-1 |
| 04 | [04_TICKET-20260706-INF-600l-2.md](./04_TICKET-20260706-INF-600l-2.md) | The mirror check is opt-in to the leafcutter agent subsystem and resolves the card path from convention, not a hardcode | INF-600l-2 | INF-600l, INF-600l-1 |
| 05 | [05_TICKET-20260706-INF-600l-3.md](./05_TICKET-20260706-INF-600l-3.md) | The pr-reviewer prose backstop for card/registry consistency delegates the search to research-agent | INF-600l-3 | INF-600l, INF-600l-1 |

## Dependencies

```
INF-600l-1 (no dependencies)
INF-600l-1-i -> INF-600l-1
INF-600l-1-ii -> INF-600l-1
INF-600l-2 -> INF-600l-1
INF-600l-3 -> INF-600l-1
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

