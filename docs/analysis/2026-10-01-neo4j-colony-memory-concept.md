---
title: "Leafcutter Neo4j Colony Memory Concept - Part 1 of 9"
description: "The user's Neo4j knowledge graph and colony memory concept (received 2026-10-01), verbatim in-tree copy, part 1 of 9: status, mandatory Stage 0 note, executive decision, vision, mission and why it can outperform (sections 1-4). Proposal under Stage 0 review, not a decision."
type: reference
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
---

> The user's concept, verbatim. Source: workspace file `leafcutter_neo4j_colony_memory_concept.md` (2,096 lines, 2026-10-01). Part 1 of 9 (first part | [next part](2026-10-01-neo4j-colony-memory-concept-2-layers-truth-sync.md)); split only at top-level headings for the 300-line doc limit, text unchanged. Stage 0 review: [delta design](2026-10-01-colony-memory-stage0-delta.md).

# Leafcutter Neo4j Knowledge Graph & Colony Memory Concept

**Status:** Proposed architecture / ADR candidate  
**Supersedes:** Earlier proposal to use PostgreSQL / Supabase as the primary Colony Memory store  
**Primary decision:** Evaluate Neo4j as Leafcutter's combined queryable knowledge graph and persistent learned memory  
**Canonical declared knowledge:** Git repository (YAML / Markdown / code / tests)  
**Execution history:** Langfuse  
**Learned / relational memory:** Neo4j  
**MVP principle:** Neo4j must remain optional; Leafcutter core must still work without a configured memory backend.

> [!IMPORTANT]
> ## Stage 0 is mandatory: verify this against Leafcutter's current design
>
> This document is **not yet permission to build a parallel knowledge system**.
>
> Before implementation, the proposal **MUST be checked against the current Leafcutter codebase and data model**, especially:
>
> - the current capability registry;
> - existing graph / workflow abstractions;
> - existing knowledge and component representations;
> - current YAML / Markdown conventions;
> - existing ID and namespacing rules;
> - acceptance-criteria storage and lifecycle;
> - AC ↔ test linking;
> - ADR and policy storage;
> - architecture diagrams and documentation structure;
> - repository indexing and search;
> - persistence abstractions;
> - any existing database / cache / graph implementation;
> - existing PO, documentation, architecture, QA, and other role/capability workflows.
>
> **Reuse and extend what Leafcutter already has. Do not duplicate it.**
>
> Stage 0 must produce an implementation delta: what can be reused as-is, what must be adapted, and what genuinely needs to be added.

---

# 1. Executive decision

The earlier design direction of using **PostgreSQL / Supabase as the primary Colony Memory** should be reverted.

That decision made sense while Colony Memory looked mainly like:

- capability counters;
- routing statistics;
- decision outcome rows;
- vector similarity over previous decisions.

The model has since evolved substantially.

Leafcutter memory is increasingly about **relationships**:

- a decision uses evidence;
- evidence comes from ADRs, policies, documentation, code, or research;
- a decision applies to components and workflows;
- a decision may later be corrected;
- a correction can reveal a missing criterion;
- a bug can be caused by a wrong or missing decision;
- a bug can teach a lesson;
- a lesson applies to specific actions, components, frameworks, workflows, or decision types;
- acceptance criteria are implemented by code and verified by tests;
- workflows invoke capabilities;
- capabilities produce outcomes;
- outcomes strengthen or weaken future routing choices;
- recurring reasoning can become policy;
- recurring policy paths can become workflows;
- stable workflows can eventually become deterministic implementation.

This is naturally a **graph-shaped memory system**.

PostgreSQL can represent such a system, but Leafcutter would increasingly have to build its own graph traversal, relationship mapping, join model, identity management, and semantic expansion layer.

**Proposed architecture:**

```text
Git / Repository
    = declared, reviewable, versioned engineering knowledge

Neo4j
    = compiled/queryable knowledge graph
      + persistent Colony Memory
      + decision precedents
      + mistakes / lessons / patterns

Langfuse
    = raw execution history
      + traces
      + model / Jev calls
      + evaluation
      + runtime debugging
```

---

# 2. Vision

## Vision statement

**Leafcutter turns engineering experience into structure.**

AI engineering should not repeatedly start from raw intelligence and rediscover the same process. Leafcutter should accumulate evidence from features, bugs, decisions, reviews, tests, research, and production outcomes, and progressively convert that experience into:

1. better decision context;
2. better policies;
3. better workflows;
4. more deterministic checks;
5. new specialized capabilities;
6. less repeated open-ended LLM reasoning.

The long-term system should behave more like a learning organization or colony than a stateless coding agent.

## The central thesis

Current AI agents repeatedly spend intelligence rediscovering:

- what they should inspect;
- which questions matter;
- which decisions exist;
- what evidence is relevant;
- what should be tested;
- whether documentation changes;
- which previous architecture decisions matter;
- what failure means.

When the session ends, much of that reasoning disappears.

Leafcutter should instead compound engineering knowledge:

```text
LLM reasoning
     ↓
captured decision
     ↓
repeated pattern
     ↓
policy / checklist
     ↓
repeated policy execution
     ↓
workflow
     ↓
proven invariant
     ↓
deterministic implementation
```

The individual model does not need to become dramatically more intelligent.

**The system around the model gets better every time it operates.**

---

# 3. Mission

Leafcutter's mission is to create a development runtime that combines:

- deterministic invariants where facts can be computed;
- explicit workflows where the process is known;
- policies / checklists where required considerations are known but context determines the path;
- Jev for bounded semantic decisions against known criteria;
- LLMs for genuine synthesis, generation, option creation, and unresolved reasoning;
- humans for preference, authority, risk acceptance, and genuinely unresolved product decisions;
- persistent organizational memory so future work benefits from previous work.

The mission is **not** to replace human engineering judgment with a model.

The mission is to stop losing engineering judgment after each task.


# 4. Why this can outperform common human + coding-agent workflows

The expected advantage is not simply that Jev, LangGraph, Neo4j, Claude, or Codex is individually "smarter" than a senior engineer.

The advantage is **accumulation and consistency**.

Human software development routinely loses knowledge:

> Last time we changed this component, we forgot timeout behavior.

Perhaps somebody remembers it.

Perhaps it becomes a comment.

Perhaps it becomes an ADR.

Perhaps someone adds it to a checklist.

Perhaps the engineer leaves.

Two years later somebody asks:

> Why did we build it this way?

The learning existed, but it was not reliably converted into executable organizational knowledge.

Leafcutter should create a stronger loop:

```text
                    EXPERIENCE

Feature / Bug / Decision
          │
          ▼
       Decisions
          │
          ▼
      Implementation
          │
          ▼
       Outcome
          │
          ▼
   Was it successful?
          │
     ┌────┴────┐
     ▼         ▼
    YES        NO
     │          │
     │      what failed?
     │          │
     └────┬─────┘
          ▼
       LEARNING
          │
 ┌────────┼──────────┐
 ▼        ▼          ▼
routing  policy    capability
stats    update       gap
 │        │          │
 └────────┼──────────┘
          ▼
     Colony Memory
          │
          ▼
    NEXT DECISION
```

**Experience does not merely inform the next engineer. It modifies the environment in which the next decision is made.**

That is close to the stigmergic learning pattern of an ant colony: useful paths are reinforced through successful use while dead ends decay.

---

