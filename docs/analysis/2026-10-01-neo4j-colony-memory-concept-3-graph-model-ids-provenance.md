---
title: "Leafcutter Neo4j Colony Memory Concept - Part 3 of 9"
description: "The user's Neo4j knowledge graph and colony memory concept (received 2026-10-01), verbatim in-tree copy, part 3 of 9: graph model, Git-native ACs, identity, provenance, retrieval over YAML (sections 9-13). Proposal under Stage 0 review, not a decision."
type: reference
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
---

> The user's concept, verbatim. Source: workspace file `leafcutter_neo4j_colony_memory_concept.md` (2,096 lines, 2026-10-01). Part 3 of 9 ([previous part](2026-10-01-neo4j-colony-memory-concept-2-layers-truth-sync.md) | [next part](2026-10-01-neo4j-colony-memory-concept-4-retrieval-and-memory-capture.md)); split only at top-level headings for the 300-line doc limit, text unchanged. Stage 0 review: [delta design](2026-10-01-colony-memory-stage0-delta.md).

# 9. Neo4j graph model

> [!IMPORTANT]
> The following schema is a **starting proposal** and MUST be mapped against Leafcutter's existing concepts before implementation.

## 9.1 Declared / source-derived node types

```text
(:Repository)
(:Component)
(:AcceptanceCriterion)
(:ADR)
(:Policy)
(:Workflow)
(:Capability)
(:Document)
(:ArchitectureArtifact)
(:File)
(:Class)
(:Function)
(:API)
(:Test)
```

Not every node type must be implemented in the MVP.

Reuse existing Leafcutter abstractions where available.

## 9.2 Learned node types

```text
(:Decision)
(:DecisionType)
(:Evidence)
(:Mistake)
(:Lesson)
(:Bug)
(:CapabilityOutcome)
(:CapabilityGap)
(:ExecutionPattern)
(:Memory)
```

## 9.3 Candidate relationships

```text
CONTAINS
BELONGS_TO
HAS_AC
IMPLEMENTS
IMPLEMENTED_BY
VERIFIES
TESTED_BY
USES
CALLS
DEPENDS_ON
AFFECTS
ABOUT
APPLIES_TO
USED_EVIDENCE
USED_POLICY
SUPPORTED_BY
CONTRADICTED_BY
RESULTED_IN
CORRECTED_BY
CAUSED
TAUGHT
CONFIRMS
VIOLATES
SUPERSEDES
TRIGGERED
RELATED_TO
PRODUCED_BY
```

The relationship vocabulary should be deliberately constrained and versioned.

Do not create arbitrary relationship names from LLM output.

---

# 10. Acceptance criteria remain Git-native

One of Leafcutter's strongest design properties should remain:

> **Code ships with its acceptance criteria.**

Example:

```yaml
component: retrieval

acceptance_criteria:
  - id: ac:retrieval:cache.force_refresh
    statement: >
      Force refresh bypasses an existing cached result.

  - id: ac:retrieval:cache.ttl
    statement: >
      Cached retrieval results expire according to the configured TTL.
```

Tests can explicitly reference ACs:

```python
@acceptance_criteria("ac:retrieval:cache.force_refresh")
def test_force_refresh_bypasses_cache():
    ...
```

Neo4j then compiles these relationships:

```text
(:Component {id: "component:retrieval"})
      │
      └─[:HAS_AC]─►(:AcceptanceCriterion {
                       id: "ac:retrieval:cache.force_refresh"
                     })

(:Test {id: "..."})
      │
      └─[:VERIFIES]─►(:AcceptanceCriterion)
```

This makes queries such as these straightforward:

- Which ACs have no tests?
- Which tests verify this AC?
- Which functions implement this AC?
- Which bugs affected this AC?
- Which decisions were previously made around this AC?
- Which lessons should be injected before modifying this AC?


# 11. Identity strategy

Neo4j does not eliminate the need for identity, but it lets Leafcutter keep the identity model small and explicit.

## 11.1 Stable semantic IDs

Objects whose identity should survive refactoring should have explicit repository-controlled IDs:

```text
component:retrieval
ac:retrieval:cache.force_refresh
adr:retrieval:caching-strategy
policy:langgraph:parallel-failure
workflow:new-feature
capability:decision-research
```

Likely candidates:

- Component
- AcceptanceCriterion
- ADR
- Policy
- Workflow
- Capability

## 11.2 Derived code IDs

Physical implementation objects can use deterministic derived identities:

```text
file:<repo>:<path>
class:<repo>:<module>:<qualified_name>
function:<repo>:<module>:<qualified_name>
test:<repo>:<module>:<qualified_name>
```

Developers should not manually maintain these.

## 11.3 Learned-object IDs

Learned entities can use generated IDs:

```text
decision:<uuid>
lesson:<uuid>
mistake:<uuid>
capability-outcome:<uuid>
```

## 11.4 Rule

> **Only entities whose conceptual identity must survive refactoring require a manually declared semantic ID.**

Neo4j constraints must enforce uniqueness for canonical ID properties.

---

# 12. Provenance and versioning

Every source-derived node must be traceable back to Git.

Recommended provenance:

```text
origin = "repository"
repository_id
path
commit_sha
branch_or_ref
source_type
last_indexed_at
schema_version
```

Every learned node should record equivalent operational provenance:

```text
origin = "learned"
root_task_id
langfuse_trace_id
created_at
created_by_capability
policy_version
framework_version where relevant
repository_revision
```

This makes decisions reproducible:

> What did Leafcutter know when it made this decision?

---

# 13. Why Neo4j improves retrieval over YAML-only graphs

YAML remains excellent for authoring.

It is less suitable as the runtime graph engine.

With YAML-only retrieval, Leafcutter has to implement:

```text
load files
→ understand schemas
→ resolve IDs
→ find references
→ traverse relationships
→ recursively open more files
→ deduplicate
→ apply semantic ranking
→ stop traversal
```

With Neo4j, graph traversal is the database's native responsibility.

Example need:

> Give me the ACs affected by this component, the tests verifying them, and previous mistakes involving them.

Conceptual Cypher:

```cypher
MATCH (c:Component {id: $component_id})
      -[:HAS_AC]->(ac:AcceptanceCriterion)
OPTIONAL MATCH (t:Test)-[:VERIFIES]->(ac)
OPTIONAL MATCH (m:Mistake)-[:AFFECTS]->(ac)
RETURN ac, collect(t), collect(m)
```

The larger advantage is not syntax alone.

It is that the relationship model itself is queryable without rebuilding a graph engine in application code.

---

