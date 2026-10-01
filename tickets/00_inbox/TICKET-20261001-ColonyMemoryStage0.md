---
title: "Colony memory Stage 0: in-tree Neo4j concept and delta design for review"
status: in_progress
components:
  - knowledge_management
  - knowledge_system
created: 2026-10-01
depends_on: []
priority: high
roadmap_phase: phase_1
requires_diagram: false
requires_adr: false
change_target: docs
risk_surface: internal
tags:
  - colony-memory
  - neo4j
  - stage-0
  - docs-only
last_updated: 2026-10-01
files_touched:
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-2-layers-truth-sync.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-3-graph-model-ids-provenance.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-4-retrieval-and-memory-capture.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-5-reinforcement-and-gaps.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-6-deployment-diagrams-mvp.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-7-roadmap-and-l0-acs.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-8-adrs-and-propagation.md
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept-9-business-risks-next-action.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md
  - docs/INDEX.md
  - tickets/00_inbox/TICKET-20261001-ColonyMemoryStage0.md
agents:
  commit: needed
---

# Colony memory Stage 0: in-tree Neo4j concept and delta design for review

## Actor / Goal
In order to decide whether and how Neo4j becomes Leafcutter's knowledge graph and colony memory
without building a parallel knowledge system, we need the user's concept in the tree and a Stage 0
delta design that checks it against what Leafcutter already has, so that the user can make the
open decisions before any ADR, schema or code is written.

## Context
- **Concept (verbatim, the user's):** the workspace file `leafcutter_neo4j_colony_memory_concept.md`
  (2,096 lines, 2026-10-01), copied in-tree in nine parts, starting at
  [part 1](../../docs/analysis/2026-10-01-neo4j-colony-memory-concept.md) and ending at
  [part 9](../../docs/analysis/2026-10-01-neo4j-colony-memory-concept-9-business-risks-next-action.md).
  Only frontmatter and a one-line header note were added; the split is at top-level headings.
- **Delta design (Stage 0 output, concept §29 and §38):** four parts:
  - [summary and the ten answers](../../docs/analysis/2026-10-01-colony-memory-stage0-delta.md)
  - [reuse table and minimal MVP](../../docs/analysis/2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md)
  - [lessons, ADR plan and ownership](../../docs/analysis/2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md)
  - [decisions needed](../../docs/analysis/2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md)
- **Grounding:**
  - three read-only Stage 0 research passes over main @ 73dce349, kernel V0 (PR #973) and the
    user's `kernel-bootstrap-v0` worktree (ADR-057/058, uncommitted);
  - the kernel V0 live-QA lessons of 2026-10-01.
- **Binding decisions:**
  1. This ticket exists to satisfy the ticket mandate. It carries **no acceptance criteria by user
     decision** and does not go through `/plan-feature`.
  2. Docs only.

## Scope (no acceptance criteria by user decision)
- Add the concept in-tree, verbatim, in parts with navigation links (300-line doc limit).
- Add the Stage 0 delta design:
  - answers to the concept's ten questions;
  - a reuse / adapt / replace / add table;
  - the minimal Neo4j MVP;
  - the lessons mapping, including the approval-provenance gap;
  - the ADR plan (ADR-059..061);
  - ownership and propagation;
  - the eight decisions needed from the user, each with a recommendation.

## Out of Scope
- Writing or amending any ADR (ADR-056..061). The plan waits on the user's decisions.
- Finalising any Neo4j schema, constraint or index.
- Code, config, roadmap, vision, AC, component-registry or glossary edits.
- Any change in the `kernel-bootstrap-v0` worktree.

## Risk & Safety
- Touches money? No.
- Touches data? No. New documentation files only.
- Reversibility? Fully reversible: delete the added files.

## Comments

_(Append-only log — leave blank when authoring.)_
