---
title: "Leafcutter Neo4j Colony Memory Concept - Part 7 of 9"
description: "The user's Neo4j knowledge graph and colony memory concept (received 2026-10-01), verbatim in-tree copy, part 7 of 9: roadmap stages 0-7 and the fifteen L0 acceptance criteria (sections 30-31). Proposal under Stage 0 review, not a decision."
type: reference
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
---

> The user's concept, verbatim. Source: workspace file `leafcutter_neo4j_colony_memory_concept.md` (2,096 lines, 2026-10-01). Part 7 of 9 ([previous part](2026-10-01-neo4j-colony-memory-concept-6-deployment-diagrams-mvp.md) | [next part](2026-10-01-neo4j-colony-memory-concept-8-adrs-and-propagation.md)); split only at top-level headings for the 300-line doc limit, text unchanged. Stage 0 review: [delta design](2026-10-01-colony-memory-stage0-delta.md).

# 30. Roadmap

## Stage 0 — Align with current Leafcutter

**Goal:** prevent duplicate architecture.

Outputs:

- current-state map;
- gap analysis;
- ID mapping;
- storage mapping;
- artifact ownership mapping;
- confirmed MVP schema;
- initial ADRs.

## Stage 1 — Neo4j query graph MVP

**Goal:** compile declared repository knowledge and connect decisions to it.

Deliver:

- optional Neo4j backend;
- merge ingestion;
- Component / AC / ADR / Policy graph;
- basic test linkage where available;
- basic Cypher retrieval;
- Decision storage;
- CapabilityGap storage;
- Langfuse linking.

## Stage 2 — Memory Capture

**Goal:** stop losing reusable execution learning.

Deliver:

- memory capture workflow;
- Mistake;
- Lesson;
- correction relationships;
- scope / APPLIES_TO relationships;
- first post-bug learning flow.

## Stage 3 — Semantic precedent memory

**Goal:** let current decisions benefit from similar past decisions.

Deliver:

- decision embeddings;
- vector indexes;
- similar-decision retrieval;
- corrected-decision retrieval;
- read-only precedent context injected into Jev decisions.

Historical precedents should inform decisions but not yet change routing automatically.

## Stage 4 — Colony reinforcement

**Goal:** derive evidence-based path and capability performance.

Deliver:

- outcome scoring;
- short / medium / long-term success evidence;
- confidence calibration;
- negative outcome tracking;
- decay model;
- capability/path statistics;
- route suggestions.

Start with **observe → analyze → suggest**.

Only later allow learned data to influence routing.

## Stage 5 — Knowledge crystallization

**Goal:** convert recurring experience into durable engineering process.

Deliver:

```text
Memory → Lesson → Policy Candidate → Workflow Candidate
```

Add review / promotion flows that create normal Git PRs.

## Stage 6 — Versioned / proposed knowledge

**Goal:** reason over knowledge that is not yet merged.

Potentially add:

- PR overlays;
- branch projections;
- local workspace overlays;
- DRAFT / PROPOSED / MERGED / REJECTED lifecycle.

## Stage 7 — Managed Colony Memory

**Goal:** offer a zero-install memory product.

Deliver:

- managed Leafcutter memory API;
- Neo4j hidden behind service;
- tenant isolation;
- backup / upgrade management;
- organization shared memory;
- dashboards and analytics;
- paid plan / enterprise option.


# 31. L0 acceptance criteria

These are **product-level L0 ACs**, not implementation-level ACs.

They must be reviewed and adapted by the current Leafcutter PO / requirements workflow.

## L0-AC-01 — Git remains canonical for declared knowledge

Leafcutter must keep intentionally authored engineering knowledge versioned with the repository.

## L0-AC-02 — Neo4j is rebuildable from declared knowledge

Loss of source-derived Neo4j data must not destroy canonical ACs, ADRs, policies, or workflows.

## L0-AC-03 — Learned knowledge is persistent and relational

Leafcutter must be able to store decisions, corrections, mistakes, lessons, capability gaps, and their relationships to declared project knowledge.

## L0-AC-04 — Every learned decision is traceable

A stored decision must identify the execution / Langfuse trace and repository knowledge context from which it was made.

## L0-AC-05 — ACs remain colocated with development

Acceptance criteria must continue to ship through the normal repository / PR lifecycle rather than becoming Neo4j-only records.

## L0-AC-06 — AC verification is queryable

Leafcutter must be able to determine which tests verify an AC where such mappings exist.

## L0-AC-07 — Neo4j is optional

Leafcutter core workflows must continue to function when no Colony Memory backend is configured.

## L0-AC-08 — Memory is scoped

Leafcutter must retrieve memory based on relevant action / component / workflow / decision context rather than injecting one global memory.

## L0-AC-09 — Mistakes create reusable learning opportunities

Wrong decisions, overrides, bugs, or rework must be representable as reusable learned knowledge.

## L0-AC-10 — Historical popularity is not treated as correctness

Usage count alone must never strengthen a capability path or decision precedent.

## L0-AC-11 — Corrections preserve original context

When a decision is later corrected, Leafcutter must preserve the original evidence and the reason the later outcome differed.

## L0-AC-12 — Historical influence can weaken

The design must allow obsolete decisions / patterns to be superseded, contradicted, or decayed as context changes.

## L0-AC-13 — Learned knowledge can be promoted

Repeatedly validated lessons must be promotable into repository-controlled policy / ADR / workflow changes through a normal PR process.

## L0-AC-14 — The graph model is constrained

LLMs must not create arbitrary node labels, relationship types, or canonical IDs without schema / capability validation.

## L0-AC-15 — Current Leafcutter architecture takes precedence

No implementation may introduce a parallel registry, duplicate AC model, duplicate ID system, or redundant knowledge abstraction without first proving that the existing Leafcutter capability cannot be reused or extended.


