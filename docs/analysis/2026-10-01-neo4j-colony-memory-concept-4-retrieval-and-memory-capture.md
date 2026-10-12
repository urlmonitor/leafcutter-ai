---
title: "Leafcutter Neo4j Colony Memory Concept - Part 4 of 9"
description: "The user's Neo4j knowledge graph and colony memory concept (received 2026-10-01), verbatim in-tree copy, part 4 of 9: LLM/Jev operability, precedent memory, action-scoped memory, capture graph, mistakes (sections 14-18). Proposal under Stage 0 review, not a decision."
type: reference
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
---

> The user's concept, verbatim. Source: workspace file `leafcutter_neo4j_colony_memory_concept.md` (2,096 lines, 2026-10-01). Part 4 of 9 ([previous part](2026-10-01-neo4j-colony-memory-concept-3-graph-model-ids-provenance.md) | [next part](2026-10-01-neo4j-colony-memory-concept-5-reinforcement-and-gaps.md)); split only at top-level headings for the 300-line doc limit, text unchanged. Stage 0 review: [delta design](2026-10-01-colony-memory-stage0-delta.md).

# 14. LLM / Jev operability

Neo4j creates a bounded interface that models can understand more easily than arbitrary repository navigation.

Instead of teaching a model:

- folder conventions;
- file naming;
- YAML schemas;
- reference syntax;
- recursive lookup;
- stopping rules;

Leafcutter can expose a compact graph schema:

```text
Nodes:
Component
AcceptanceCriterion
Test
ADR
Policy
Decision
Lesson

Relationships:
HAS_AC
VERIFIES
USES
AFFECTS
CORRECTED_BY
TAUGHT
APPLIES_TO
```

However, Leafcutter should **not default to unconstrained model-generated Cypher**.

Preferred order:

```text
1. Registered parameterized graph queries
2. Generic query templates
3. Bounded query-plan generation
4. Text-to-Cypher only as fallback / research capability
```

Example registered retrieval capabilities:

```text
get_component_context(component_id)
get_related_acceptance_criteria(component_id)
get_affected_tests(ac_ids)
get_decision_precedents(decision_type, context)
get_related_lessons(action, components)
get_policy_context(component_ids, action)
```

The model decides **what information it needs**.

The retrieval capability decides **how to get it**.


# 15. Vector search and decision precedent memory

Neo4j should eventually store vector embeddings for relevant learned objects, particularly decisions.

A decision must store more than its final answer.

Example:

```text
Decision
├── question
├── decision_type
├── task_context
├── options
├── criteria
├── evidence
├── selected_option
├── confidence
├── final_outcome
├── corrections
├── correction_reason
└── embedding(s)
```

Potentially maintain separate representations for:

### Context similarity

> Have we faced a similar situation before?

### Criteria similarity

> Were similar considerations important before?

Decision flow:

```text
New decision
    │
    ├── current evidence
    ├── current ADR / policy
    └── similar historical decisions
                 │
                 ▼
                Jev
                 │
                 ▼
          supported decision
```

Corrected decisions are especially valuable.

Example:

```text
Original:
SUBGRAPH, confidence .94

Later correction:
NODE

Reason:
reuse was over-weighted;
the capability had no independent lifecycle
```

A future semantically similar decision should retrieve that failure lesson.

---

# 16. Memory should be action-scoped, not globally injected

Leafcutter should not ask:

> What memories are similar to this prompt?

Instead:

> Which memories are relevant to the action or decision I am about to perform?

Examples:

## Node-vs-subgraph decision

Retrieve:

- previous node/subgraph decisions;
- corrected node/subgraph decisions;
- relevant ADRs;
- mistakes involving graph boundaries;
- applicable LangGraph policies.

Ignore unrelated memory.

## Writing retrieval tests

Retrieve:

- previous retrieval bugs;
- recurring missed edge cases;
- retrieval test policies;
- historically failing scenarios;
- ACs affected by the change.

This is one reason graph relationships are valuable: scope is represented by connections rather than one global memory document.

---

# 17. Memory Capture Graph

Memory capture should become a first-class Leafcutter workflow.

```text
EVENT
  │
  ▼
Could something reusable be learned?
        [Jev]
  │
  ├── NO → Langfuse trace only
  │
  └── YES
        │
        ▼
What kind of learning?
        │
        ├─ decision precedent
        ├─ mistake / failure lesson
        ├─ engineering rule
        ├─ workflow pattern
        ├─ capability gap
        ├─ retrieval association
        └─ architectural knowledge
        │
        ▼
Where does it apply?
        │
        ├─ repository
        ├─ component
        ├─ workflow
        ├─ decision type
        ├─ capability
        ├─ artifact
        └─ global only when truly universal
        │
        ▼
Already known / related?
        │
        ├─ graph traversal
        └─ vector search
        │
   ┌────┴────┐
   │         │
  YES        NO
   │         │
reinforce   create
/update     candidate
   │         │
   └────┬────┘
        ▼
   Colony Memory
```

Memory creation is not:

> Write another Markdown file.

It is:

> Extract reusable experience and attach it to the situations where it is useful.

---

# 18. Mistakes are high-value memory

Failure memory should preserve causality.

Example:

```json
{
  "type": "decision_correction",
  "decision_type": "node_vs_subgraph",
  "original_decision": "subgraph",
  "original_confidence": 0.94,
  "original_evidence": [
    "multiple internal steps",
    "possible reuse"
  ],
  "final_decision": "node",
  "failure_reason": "No independent lifecycle or state ownership existed.",
  "missing_criterion": "independent_lifecycle"
}
```

The important memory is not:

> Sometimes use a node.

The important memory is:

> We previously chose a subgraph under similar conditions because we over-weighted reuse and omitted lifecycle independence.

This is reusable engineering knowledge.


