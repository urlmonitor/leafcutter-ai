---
title: "EPIC: MermaidComplexityGuard — Deterministic + Agentic Diagram Complexity Defense"
type: epic
status: inbox
components:
  - commit_guardian
  - architecture_docs
created: 2026-05-26
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
---

# EPIC: MermaidComplexityGuard

Prevent architecture diagrams from becoming unreadable by enforcing complexity
limits at two layers: a deterministic pre-commit hook that counts structural
elements (nodes, edges, participants, subgraphs) and warns or blocks when
thresholds are exceeded, and agentic guidelines that enforce a "Single
Responsibility Principle for Diagrams" — one concept, one flow, or one boundary
per diagram.

## Context

Architecture diagrams currently have no complexity ceiling. A single diagram can
mix unrelated concerns (e.g. Entra login flow + in-app authoring flow) into one
unreadable wall of boxes. The existing ">15 lifeline" escape hatch in
write-c4-diagram §9 is the only threshold, and it only covers sequence diagrams
switching to PlantUML — it does not encourage splitting into multiple Mermaid
diagrams.

## Decided Design (Locked — Do Not Re-Debate)

### Two Independent Layers

1. **Ticket 01 — Pre-commit hook** (`check_mermaid_complexity.py`): regex-based
   element counting per diagram type, configurable thresholds, warn-only by
   default. No Mermaid AST parser — regex patterns are sufficient for structural
   element counting.

2. **Ticket 02 — Agentic guidelines**: a new "Single Concept Rule" section in
   the write-c4-diagram skill and a matching guardrail step in the
   architecture-diagram-author agent prompt.

These two tickets are **independent** — no dependency between them, different
file sets, can be built in parallel.

### Complexity Thresholds (Ticket 01)

| Diagram Type | Metric | Threshold |
|---|---|---|
| flowchart / C4 | nodes | 15 |
| flowchart / C4 | edges | 20 |
| sequenceDiagram | participants | 8 |
| sequenceDiagram | interactions | 25 |
| erDiagram | tables | 12 |
| stateDiagram | states | 10 |
| classDiagram | classes | 10 |
| all types | subgraphs / boundaries | 4 |

### Split Criteria (Ticket 02)

A diagram MUST be split when any of these apply:
1. **Distinct actors** — >1 actor initiates an independent flow
2. **Distinct temporal phases** — "first X, then later Y" where both are self-contained
3. **Distinct bounded contexts** — two contexts connected only by a token/session/API handoff

Example: "Entra login" and "in-app authoring" are separate diagrams — distinct
temporal phases and bounded contexts, connected only by session token.

## Sub-Tickets

| # | File | Title | Depends On |
|---|---|---|---|
| 01 | `01_precommit_hook.md` | Pre-commit hook: check-mermaid-complexity | — |
| 02 | `02_agentic_guidelines.md` | Agentic split guidelines in skill + agent prompt | — |
