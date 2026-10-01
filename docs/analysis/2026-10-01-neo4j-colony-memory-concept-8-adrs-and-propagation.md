---
title: "Leafcutter Neo4j Colony Memory Concept - Part 8 of 9"
description: "The user's Neo4j knowledge graph and colony memory concept (received 2026-10-01), verbatim in-tree copy, part 8 of 9: ADR candidates A-I and required artifact propagation (sections 32-33). Proposal under Stage 0 review, not a decision."
type: reference
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
---

> The user's concept, verbatim. Source: workspace file `leafcutter_neo4j_colony_memory_concept.md` (2,096 lines, 2026-10-01). Part 8 of 9 ([previous part](2026-10-01-neo4j-colony-memory-concept-7-roadmap-and-l0-acs.md) | [next part](2026-10-01-neo4j-colony-memory-concept-9-business-risks-next-action.md)); split only at top-level headings for the 300-line doc limit, text unchanged. Stage 0 review: [delta design](2026-10-01-colony-memory-stage0-delta.md).

# 32. ADRs to create / update

These should be created through Leafcutter's existing architecture / ADR workflow after Stage 0 validates the current design.

## ADR candidate A — Colony Memory backend

**Decision question:**  
Should Leafcutter use Neo4j rather than PostgreSQL / Supabase as the primary persistent Colony Memory and knowledge-graph backend?

**Current proposal:** Neo4j.

**Supersedes:** PostgreSQL / Supabase primary-memory proposal.

## ADR candidate B — Source of truth

**Decision question:**  
Which information is canonical in Git and which is canonical in learned memory?

**Proposed rule:**

- declared engineering knowledge → Git;
- compiled declared graph → Neo4j derived;
- learned organizational memory → Neo4j;
- execution trace → Langfuse.

## ADR candidate C — Deterministic vs Jev vs LLM vs Human

**Proposed rule:**

- deterministic when exact computation / verification is possible;
- Jev for bounded semantic decisions with known options / criteria;
- LLM for generation, synthesis, option creation, or open-ended reasoning;
- human for authority, preference, risk acceptance, or unresolved product choices.

## ADR candidate D — Workflow vs policy/checklist vs LLM

**Proposed rule:**

- workflow when the process and branches are known;
- policy/checklist when required considerations are known but execution remains contextual;
- LLM-guided execution when the process is still being discovered;
- repeated LLM behavior should be evaluated for extraction into policy;
- repeated policy paths should be evaluated for extraction into workflow.

## ADR candidate E — ID model

Define:

- explicit semantic IDs;
- derived code IDs;
- generated learned IDs;
- uniqueness rules;
- namespaces.

## ADR candidate F — Merge-driven graph ingestion

Define main-branch merge as the initial canonical synchronization boundary.

## ADR candidate G — Memory lifecycle

Define:

```text
Observation → Memory → Lesson → Policy → Workflow → Deterministic
```

and the promotion / review requirements.

## ADR candidate H — Reinforcement safety

Define:

- success is not equal to merge;
- immediate / short-term / long-term outcomes;
- negative evidence;
- confidence calibration;
- decay;
- no popularity-only reinforcement.

## ADR candidate I — Managed memory abstraction

Define the backend abstraction that allows:

- no memory;
- customer-managed Neo4j;
- Neo4j Aura;
- future Leafcutter Managed Colony Memory.


# 33. Required artifact propagation

This concept is broad enough that it must **not live only in this architecture document**.

After Stage 0, the relevant existing Leafcutter roles / capabilities should propagate the validated concept into the normal product artifacts.

> [!IMPORTANT]
> The role names below are descriptive. **Use Leafcutter's actual registered capabilities / workflows after inspecting the current system. Do not invent duplicate agents if equivalent capabilities already exist.**

## Product Owner / product-planning capability

Update / create:

- Leafcutter vision;
- Leafcutter mission;
- product principles;
- roadmap;
- L0 acceptance criteria;
- capability roadmap;
- commercial managed-memory option;
- MVP scope and explicit non-goals.

## Architecture / ADR capability

Update / create:

- ADRs listed above;
- knowledge ownership model;
- source-of-truth rules;
- Neo4j graph schema;
- memory backend abstraction;
- ingestion architecture;
- versioning / provenance;
- reinforcement-safety design;
- future PR overlay design.

## Documentation expert capability

Update:

- architecture overview;
- terminology;
- Colony Memory concept;
- setup documentation;
- optional Neo4j configuration;
- self-hosted vs managed-memory model;
- explanation of Git vs Neo4j vs Langfuse responsibilities.

## Diagram / architecture-documentation capability

Maintain at least:

1. Git ↔ Neo4j ↔ Langfuse architecture diagram;
2. knowledge graph model;
3. memory capture loop;
4. crystallization lifecycle;
5. future managed-memory deployment diagram.

## Requirements / AC capability

Convert the validated L0 ACs into Leafcutter's actual AC format and link them to:

- components;
- roadmap items;
- implementation work;
- tests.

## QA / test capability

Define how the following will be tested:

- graph ingestion correctness;
- duplicate prevention;
- provenance;
- AC ↔ test links;
- decision traceability;
- memory scoping;
- optional-memory behavior;
- rebuild behavior;
- schema constraints.

## Kernel / workflow capability

Ensure the kernel can retrieve:

- declared knowledge;
- learned memory;
- prior decision precedent;
- memory-backed evidence;

without becoming tightly coupled to Neo4j-specific implementation details.


