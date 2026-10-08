---
title: "ADR-065 Amendment 1: colony statistics are rebuilt on every new input, use the same Neo4j, and each installation has its own store"
date: "2026-10-02"
time: "14:04"
type: manual
components: 
  - colony_memory
  - decision_kernel
summary: "The open questions about Leafcutter's learned statistics are answered: they are rebuilt whenever new input arrives, live in the same Neo4j as knowledge retrieval, are retried when that database is down, and every installation keeps its own store instead of sharing one with a team."
description: "Records the user's 2026-10-02 answers as ADR-065 Amendment 1: (1) aggregates are updated whenever an item that feeds them is added; (2) each update is a full rebuild, expected to be fast, with incremental maintenance only if rebuilds prove slow; (3) statistics use the same Neo4j and LEAFCUTTER_NEO4J_* settings as ADR-062's knowledge retrieval; (4) an unreachable store is retried, and because statistics are derived the next rebuild repairs a missed update, so they never block a run; (5) each installation has its own store from its own .env, with no team-shared colony memory, superseding ADR-057 section 8 and closing the shared-store privacy question. ADR-057's banner, the vision, the colony-memory layer doc, the flow overview (c2-007) and the open points (c3-022: OP-19, OP-23, OP-25) are aligned. Documentation only."
adrs: 
  - ADR-065
  - ADR-057
---

## Entry

### Changed

- `docs/architecture/adrs/ADR-065-*` — Amendment 1 records the trigger, rebuild strategy, shared Neo4j, retry and
  per-installation store; `ADR-057-*` marks section 8 superseded.
- `docs/vision.md`, `docs/architecture/components/colony-memory.md`,
  `docs/architecture/diagrams/c2-007-*` and `c3-022-*` — aligned with Amendment 1.
