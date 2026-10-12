---
title: "Leafcutter Neo4j Colony Memory Concept - Part 2 of 9"
description: "The user's Neo4j knowledge graph and colony memory concept (received 2026-10-01), verbatim in-tree copy, part 2 of 9: determinism ladder, three knowledge layers, source-of-truth rule, merge-driven sync (sections 5-8). Proposal under Stage 0 review, not a decision."
type: reference
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
---

> The user's concept, verbatim. Source: workspace file `leafcutter_neo4j_colony_memory_concept.md` (2,096 lines, 2026-10-01). Part 2 of 9 ([previous part](2026-10-01-neo4j-colony-memory-concept.md) | [next part](2026-10-01-neo4j-colony-memory-concept-3-graph-model-ids-provenance.md)); split only at top-level headings for the 300-line doc limit, text unchanged. Stage 0 review: [delta design](2026-10-01-colony-memory-stage0-delta.md).

# 5. More deterministic without becoming rigid

Pure deterministic software is predictable but can be brittle:

```text
if X:
    do Y
```

Current LLM agents are flexible but often too nondeterministic:

```text
Here is a large prompt.
Figure everything out.
```

Leafcutter should deliberately place uncertainty at the cheapest appropriate layer:

```text
        deterministic invariants
                 │
                 ▼
             workflows
                 │
                 ▼
          policies/checklists
                 │
                 ▼
                Jev
         bounded uncertainty
                 │
                 ▼
                LLM
        open-ended uncertainty
                 │
                 ▼
               Human
      authority / preference / risk
```

Rules:

- If the answer can be computed exactly, use deterministic code.
- If options and decision criteria are known, use Jev.
- If evidence is missing, retrieve or research it.
- If the criteria, options, or solution itself still need to be created, use an LLM.
- If the missing information represents human preference, authority, or risk acceptance, ask a human.
- If an LLM repeatedly follows the same reasoning pattern, attempt to extract a reusable policy.
- If policies repeatedly execute in the same successful sequence, consider creating a workflow.
- If a workflow contains stable invariants, move those invariants into deterministic code.

---

# 6. Three knowledge layers

Leafcutter should clearly separate three stores with different responsibilities.

## 6.1 Git: declared engineering truth

Git remains the source of truth for knowledge intentionally authored with the software:

- components;
- acceptance criteria;
- ADRs;
- policies;
- workflow definitions;
- capability definitions;
- architecture documentation;
- test mappings;
- other explicit engineering contracts.

Why Git remains canonical:

- branches;
- pull requests;
- review;
- diffs;
- history;
- rollback;
- merge conflict handling;
- release alignment;
- code and knowledge can ship together.

Example:

```text
retrieval/
├── component.yaml
├── acceptance-criteria.yaml
├── policies.yaml
├── architecture/
│   └── retrieval.md
├── src/
└── tests/
```

## 6.2 Neo4j: knowledge graph + Colony Memory

Neo4j becomes the primary query surface for:

### Compiled repository knowledge

Derived from Git:

- components;
- ACs;
- ADRs;
- policies;
- workflows;
- capabilities;
- tests;
- files;
- classes;
- functions;
- APIs;
- dependencies;
- relationships.

### Learned knowledge

Created from actual Leafcutter operation:

- decisions;
- corrections;
- mistakes;
- lessons;
- decision precedents;
- capability outcomes;
- capability gaps;
- recurring execution patterns;
- learned associations;
- routing performance;
- memory confidence / reinforcement.

## 6.3 Langfuse: execution history

Langfuse remains the detailed answer to:

> What happened during this execution?

It stores / traces:

- LangGraph execution;
- Jev calls;
- LLM calls;
- retrieval;
- tool calls;
- latency;
- token / cost data;
- evaluation;
- runtime failures;
- retries;
- decisions as they occurred;
- raw execution context.

Neo4j should **not** become a replacement for Langfuse.

Langfuse contains the detailed episode.

Neo4j contains the distilled organizational knowledge learned from episodes.


# 7. Source-of-truth rule

To avoid synchronization chaos, the following rule must be strict:

> **Source-derived nodes are never edited directly in Neo4j.**

If Leafcutter concludes:

> AC `cache.force_refresh` should change.

It must change the repository artifact and create a normal code / knowledge change:

```text
acceptance-criteria.yaml
```

After merge, ingestion updates Neo4j.

Conversely:

> We made a wrong architectural decision and learned something.

That is learned knowledge and may initially live only in Neo4j.

If the lesson becomes sufficiently validated, it may be **promoted** into declared knowledge:

```text
Lesson
  ↓
repeated / validated
  ↓
Policy candidate
  ↓
review
  ↓
policy.yaml / ADR / workflow
  ↓
PR
  ↓
merge
  ↓
canonical Git knowledge
  ↓
Neo4j re-index
```

This produces a clean knowledge lifecycle:

```text
Execution → Observation → Memory → Lesson → Policy → Workflow → Code
               Neo4j                Git after promotion
```

---

# 8. Merge-driven synchronization

For the MVP, keep synchronization deliberately simple.

## MVP behavior

```text
main branch
    ↓
PR merged
    ↓
CI / webhook / ingestion command
    ↓
parse changed declared-knowledge artifacts
    ↓
upsert source-derived Neo4j nodes
    ↓
update relationships
    ↓
record repository + commit provenance
    ↓
canonical graph updated
```

**Merged repository knowledge becomes canonical declared knowledge.**

The MVP does **not** need full PR overlay support.

## Later: proposed-knowledge overlays

A later version can index open PRs as non-canonical projections:

```text
Canonical main graph
        +
PR #842 proposed overlay
        +
local workspace overlay
```

Knowledge states could include:

- `DRAFT`
- `PROPOSED`
- `MERGED`
- `SUPERSEDED`
- `REJECTED`

This would allow Leafcutter to say:

> Current official architecture says A, but PR #842 proposes B.

That is useful, but should not block the initial implementation.

---

