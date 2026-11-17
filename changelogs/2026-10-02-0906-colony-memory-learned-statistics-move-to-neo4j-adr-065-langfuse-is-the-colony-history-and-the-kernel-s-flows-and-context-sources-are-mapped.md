---
title: "Colony memory: learned statistics move to Neo4j (ADR-065), Langfuse is the colony history, and the kernel's flows and context sources are mapped"
date: "2026-10-02"
time: "09:06"
type: manual
components: 
  - decision_kernel
  - colony_memory
  - roadmap
  - documentation_system
summary: "Leafcutter's learning layer is now written down end to end: Langfuse records what happened, approved decisions are reviewable records in Git, and learned statistics will live as derived aggregates in an optional Neo4j store. A set of flow and context docs shows exactly where Jev, the host model, workers and humans get their context."
description: "Lands the 2026-09-30 colony-memory documents that missed PR #973 and reconciles them with what merged since. ADR-057 (optional PostgreSQL colony store behind a ColonyMemory port) and ADR-058 (Langfuse is the colony history: every node traced, decisions scored, datasets as regression memory) are recorded; ADR-065 (new, user decision 2026-10-02) moves learned statistics to Neo4j as precomputed aggregates updated after specific actions and supersedes ADR-057 in part, keeping ADR-059's single ColonyMemory port and reusing the LEAFCUTTER_NEO4J_* settings; without a store only statistics are off while decision records and precedent keep following memory.backend. Adds the colony_memory component and its layer doc, eleven Decision Kernel flow and context docs re-checked against main (design inventory, request flows, capability lifecycle, context map per consumer including decision-store precedent, learning loop, regression memory, open points OP-01 to OP-33), the roadmap colony-memory track phase_colony_1_collect to phase_colony_5_evolve, and vision and glossary updates. Documentation only; no code change."
pr: 981
adrs: 
  - ADR-057
  - ADR-058
  - ADR-065
---

## Entry

### Added

- `docs/architecture/adrs/ADR-057`, `ADR-058`, `ADR-065` — the colony memory store (ADR-057, now
  superseded in part), Langfuse as the colony history, and learned statistics in Neo4j.
- `docs/architecture/components/colony-memory.md` and the `colony_memory` component.
- `docs/architecture/diagrams/c2-007-decision-kernel-flows-overview.md` and `c3-013` to `c3-022` (`decision-kernel-*`) — the
  design inventory, request flows, capability lifecycle, context map per consumer, learning loop,
  regression memory and open points.
- `docs/roadmap.json` — the colony-memory track `phase_colony_1_collect` to `phase_colony_5_evolve`.

### Changed

- ADR-056, ADR-057 and ADR-058 point at ADR-065; `docs/architecture/components/decision-kernel.md`
  lists the new ADRs; the ADR index is regenerated.
- `docs/vision.md`, `docs/glossary.md`, `docs/glossary_blacklist.md` and `docs/components.json` are
  aligned with ADR-065.
