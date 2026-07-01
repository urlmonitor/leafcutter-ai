---
epic_name: EPIC-SelfDescribingAgentsCorrections
created: 2026-06-08
status: in_progress
components:
  - infrastructure
source_ac: INF-600
---
# EPIC-SelfDescribingAgentsCorrections

## Goal

This epic implements the post-rollout corrections to the self-describing agents
system (INF-600), batching the leaf ACs beneath three L1s — INF-600g (build
validation gate), INF-600d (spawn-graph accuracy), and INF-600b (card content
enrichment). It consists of 10 tickets in topological build order, with all
inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260608-INF-600g-1.md](./01_TICKET-20260608-INF-600g-1.md) | Build validates that spawned_by entries are reciprocal with spawn_allowlist entries | INF-600g-1 | — |
| 02 | [02_TICKET-20260608-INF-600g-2.md](./02_TICKET-20260608-INF-600g-2.md) | Build detects phase agents redundantly listed alongside __ticket_phase_agents__ macro | INF-600g-2 | — |
| 03 | [03_TICKET-20260608-INF-600g-3.md](./03_TICKET-20260608-INF-600g-3.md) | Build cross-references skills_invoked against actual skill usage in agent template body | INF-600g-3 | — |
| 04 | [04_TICKET-20260608-INF-600g-2-i.md](./04_TICKET-20260608-INF-600g-2-i.md) | Non-phase agent individually listed alongside __ticket_phase_agents__ is valid | INF-600g-2-i | 02 (INF-600g-2) |
| 05 | [05_TICKET-20260608-INF-600g-3-i.md](./05_TICKET-20260608-INF-600g-3-i.md) | Project-local skill referenced in skills_invoked resolves via .claude/skills/ fallback | INF-600g-3-i | 03 (INF-600g-3) |
| 06 | [06_TICKET-20260629-INF-600d-1.md](./06_TICKET-20260629-INF-600d-1.md) | spawn_allowlist excludes agents whose capability is performed via a skill rather than delegation | INF-600d-1 | — |
| 07 | [07_TICKET-20260629-INF-600d-1-i.md](./07_TICKET-20260629-INF-600d-1-i.md) | Agent that delegates to a specialist for complex cases AND has a fallback skill declares both | INF-600d-1-i | 06 (INF-600d-1) |
| 08 | [08_TICKET-20260629-INF-600b-1.md](./08_TICKET-20260629-INF-600b-1.md) | Generated card includes hyperlinks to component docs and architecture references | INF-600b-1 | — |
| 09 | [09_TICKET-20260629-INF-600b-1-i.md](./09_TICKET-20260629-INF-600b-1-i.md) | Card omits hyperlinks for documents that do not exist on disk | INF-600b-1-i | 08 (INF-600b-1) |
| 10 | [10_TICKET-20260629-INF-600b-2.md](./10_TICKET-20260629-INF-600b-2.md) | Generated card surfaces per-agent AC assignments so agents can work AC-by-AC | INF-600b-2 | — |

## Dependencies

```
INF-600g-1 (no dependencies)
INF-600g-2 (no dependencies)
INF-600g-3 (no dependencies)
INF-600g-2-i → depends on INF-600g-2 (ticket 02)
INF-600g-3-i → depends on INF-600g-3 (ticket 03)
INF-600d-1 (no dependencies)
INF-600d-1-i → depends on INF-600d-1 (ticket 06)
INF-600b-1 (no dependencies)
INF-600b-1-i → depends on INF-600b-1 (ticket 08)
INF-600b-2 (no dependencies)
```

## Build batches (by files_touched + depends_on)

- **Batch 1 (parallel-safe):** 01, 02, 03 (build_phases.py / registry_validator.py),
  06 (config/agent_registry.json), 08 (generate_agent_cards.py), 10 (generate_agent_cards.py)
  — note 08 and 10 share generate_agent_cards.py, so they serialize relative to each other.
- **Batch 2:** 04 (after 02), 05 (after 03), 07 (after 06), 09 (after 08)

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| commit | 01–10 |
| pr-reviewer | 01–10 |
| pull-request | 01–10 |
| python-coder | 01–10 |
| test-runner | 01–10 |
| test-writer | 01, 02, 03, 04, 05 (g-tickets); b/d tickets per their agents map |
