---
title: "Leafcutter Neo4j Colony Memory Concept - Part 5 of 9"
description: "The user's Neo4j knowledge graph and colony memory concept (received 2026-10-01), verbatim in-tree copy, part 5 of 9: pheromone model, multi-stage success, decay, negative pheromones, gap scouts, analytics boundary (sections 19-24). Proposal under Stage 0 review, not a decision."
type: reference
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
---

> The user's concept, verbatim. Source: workspace file `leafcutter_neo4j_colony_memory_concept.md` (2,096 lines, 2026-10-01). Part 5 of 9 ([previous part](2026-10-01-neo4j-colony-memory-concept-4-retrieval-and-memory-capture.md) | [next part](2026-10-01-neo4j-colony-memory-concept-6-deployment-diagrams-mvp.md)); split only at top-level headings for the 300-line doc limit, text unchanged. Stage 0 review: [delta design](2026-10-01-colony-memory-stage0-delta.md).

# 19. Pheromone / reinforcement model

Leafcutter's ant-colony metaphor should become an explicit learning concept.

Useful capability paths should gain evidence through successful outcomes.

Bad paths should weaken.

However:

> **Usage count alone must never strengthen a path.**

Otherwise early routing mistakes become self-reinforcing.

Candidate signals:

```text
usage_count
successful_resolutions
failed_resolutions
fallback_after_use
human_corrections
decision_overrides
average_confidence
confidence_when_correct
confidence_when_wrong
cost
latency
downstream_rework
later_architecture_correction
```

The goal is not popularity.

The goal is **evidence-backed usefulness in similar contexts**.

---

# 20. Success is multi-stage

A merged PR is not proof that an architectural decision was correct.

`tests_passed == architecture_correct` is also false.

Outcome evidence should mature over time.

## Level 1 — Immediate evidence

- tests pass;
- schema validates;
- review accepted;
- ACs appear satisfied.

## Level 2 — Short-term evidence

- no immediate regression;
- no rollback;
- no rapid rework;
- no immediate AC violation.

## Level 3 — Long-term evidence

- architecture survives later changes;
- decision is not subsequently overturned;
- no recurring bug pattern emerges;
- the selected structure remains appropriate under later use.

A decision/path confidence can therefore change over time.

---

# 21. Pheromone decay

Historical success must not remain permanently dominant.

Relevant context can change:

- framework version;
- policy version;
- repository architecture;
- product requirements;
- organizational constraints.

Memory should therefore track:

```text
first_observed
last_confirmed
confirmation_count
contradiction_count
framework_version
policy_version
repository_revision
superseded_by
```

Historical influence should decay unless reconfirmed.

This prevents Leafcutter from becoming trapped by its own history.

---

# 22. Negative pheromones must preserve context

A later correction should not simply produce:

```text
Redis: -1
```

Example:

```text
Original decision:
Redis

Evidence:
high request throughput
short TTL
ephemeral state

Later decision:
Postgres

Reason:
new requirement introduced durable audit history
```

The original decision may still have been correct under the original assumptions.

Future retrieval should be able to distinguish:

```text
same original constraints
→ Redis precedent remains useful

durable audit required
→ corrected Postgres precedent is more relevant
```

This is why decision context + evidence + correction reason must be preserved.

---

# 23. Capability gaps as scouts

When the kernel returns `NO_CAPABILITY`, this is valuable colony information.

```text
Unknown task
    ↓
Capability gap
    ↓
temporary fallback / research
    ↓
did the fallback succeed?
    ↓
store pattern
```

Repeated gaps create evidence for new specialized workflows.

Example:

```text
Capability gap:
database migration impact analysis

occurrences: 47
fallback success: 91%
fallback cost: high
```

That becomes evidence to build:

```text
migration_impact_graph
```

This is how the colony gains new workers.

---

# 24. Neo4j is not the analytics warehouse

Langfuse remains responsible for detailed execution telemetry.

Neo4j stores the compact learned representation needed for future decisions.

Example properties on a `Capability` node may eventually include:

```text
usage_count
success_rate
fallback_rate
override_rate
avg_cost
avg_latency
last_evaluated_at
```

But the detailed raw events remain in Langfuse.

This avoids duplicating an observability system inside Neo4j.


