---
title: "ADR: Computed Quality Gates"
status: todo
components:
  - infrastructure
created: 2026-07-01
depends_on: []
priority: high
requires_adr: true
requires_diagram: false
agents:
  documentation-expert: needed
  adr-author: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 01: ADR — Computed Quality Gates

## Goal

Author an ADR documenting the two-axis change classification system, the (change_target, risk_surface) → guardrail-gates mapping, and the computation of the ticket-supervisor's agent map at ticket-generation time in Python. Establish the design on top of the shipped produces trait (EPIC-AgentProducesTrait, in tickets/99_done/).

## Context

Quality gates (TDD, code review, documentation) have been implemented as templates and one-off guard rules. BO-510 (agent `produces` trait) ships the ability to declare what an agent generates (code, tests, docs, etc.). This ADR documents how to lift quality gates into a computed system invariant by:

1. Classifying every change along two axes (what it touches + where the blast radius lands)
2. Mapping each (change_target, risk_surface) pair to mandatory guardrail agents
3. Computing the full ordered agent map from the classification + the work agent's produces trait
4. Materializing the computed map into ticket frontmatter at generation time

Reference ADR-001 (self-hosting boundary) — every ticket modifies leafcutter's own templates, registry, and Python scripts.

## Acceptance Criteria

- [ ] AC-Design: ADR structure (Status, Context, Decision, Consequences, Alternatives) with all required sections
- [ ] AC-2AxisModel: Documents the two-axis model (change_target with 10 values; risk_surface with 6 values)
- [ ] AC-ProducesTrait: References BO-510 (shipped produces trait) and explains how it gates TDD
- [ ] AC-MapTable: Documents the (change_target, risk_surface) → agent-gates mapping logic
- [ ] AC-Computation: Explains the Python computation in generate_ticket_from_ac.py::_build_agents_map and how it materializes into frontmatter
- [ ] AC-SelfHosting: References ADR-001 and explains the self-hosting boundary (leafcutter modifying itself)
- [ ] AC-DecisionRecorded: ADR is written to docs/architecture/adrs/ADR-NNN-computed-quality-gates.md with the correct numbering

## Comments

## Sign-offs
- [ ] documentation-expert

## Implementation Tasks

### adr-author
- [ ] Author ADR under docs/architecture/adrs/ADR-NNN-computed-quality-gates.md documenting the two-axis classification, guardrail-gates mapping table, and computation in Python

## Risk & Safety
- Touches money? No
- Touches data? No
- Reversibility? ADR is documentation only; fully reversible
