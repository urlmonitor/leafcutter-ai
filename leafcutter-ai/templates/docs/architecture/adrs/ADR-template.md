---
title: "ADR-NNN: <Short Decision Title>"
type: adr
status: active
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
components: []
affects_diagrams: []
related_docs: []
related_code: []
---

<!-- INSTRUCTIONS: Copy this file to ADR-NNN-<slug>.md (pick the next free number).
     Fill in all sections. Replace <placeholder> text. Delete comment blocks.
     The status in this frontmatter must be "active" — change to "Proposed" in the
     Status table below when you first publish; promote to "Accepted" when adopted. -->

# ADR-NNN: <Short Decision Title>

## Status

| Field | Value |
|-------|-------|
| Status | Proposed |
| Date | YYYY-MM-DD |
| Author | <author name or agent> |
| Supersedes | — |

## Context

<!-- Describe the problem, observation, or constraint that motivated this decision.
     Include: what is changing, what is at stake, what would happen without this decision.
     2–5 paragraphs or bullet points. Be specific. -->

<Describe the context here.>

## Decision

<!-- State the decision in present tense using "will" / "MUST" language.
     Each decision is a single, unambiguous commitment.
     Example: "The system MUST use TimescaleDB for all time-series storage." -->

<State the decision here.>

## Consequences

<!-- List the effects of this decision — positive, negative, and operational.
     Use three subsections:  -->

### Positive

- <Effect 1>
- <Effect 2>

### Negative / Trade-offs

- <Trade-off 1>
- <Trade-off 2>

### Operational

- <What changes in day-to-day work as a result of this decision>

## Alternatives Considered

<!-- List alternatives that were seriously considered and explicitly rejected.
     For each: short name + one-to-three-sentence rejection reason.
     Do not include alternatives that were never seriously considered. -->

| Alternative | Rejection Reason |
|-------------|-----------------|
| <Alternative 1> | <Why it was rejected> |
| <Alternative 2> | <Why it was rejected> |

## Bidirectional Links

<!-- If this decision affects a specific architecture diagram, list the diagram path
     in affects_diagrams: above AND in the diagram's related_adrs: list.
     If there are no affected diagrams, keep affects_diagrams: [] and delete this section. -->

This ADR does not directly govern a specific architecture diagram.
