---
title: "ADR: Computed Quality Gates"
status: in_progress
components:
  - infrastructure
created: 2026-07-01
depends_on: []
priority: high
requires_adr: true
requires_diagram: false
agents:
  documentation-expert: signed_off
  adr-author: signed_off
  pr-reviewer: signed_off
  commit: signed_off
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

### 2026-07-01 12:00 — adr-author (status: ok)
feedback-id: fb_2026-07-01_87654435
completion_manifest:
  adr_file_created: true
  all_sections_present: true
  status_set: true
Authored docs/architecture/adrs/ADR-017-computed-quality-gates.md (next free number after ADR-016). The ADR covers all seven ACs: full ADR structure (Status/Context/Decision/Consequences/Alternatives), the two-axis change classification model (change_target with 10 values, risk_surface with 6 values), the BO-510 produces trait and how it gates TDD guardrails, the (change_target, risk_surface) → mandatory-gate mapping table, the generation-time materialisation in _build_agents_map in generate_ticket_from_ac.py, and the ADR-001 self-hosting boundary. Handoff file written to .pending/adr_handoff.json.

### 2026-07-01 12:15 — documentation-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Verified ADR-017-computed-quality-gates.md against all 7 ACs. All criteria are fully addressed: ADR structure (Status/Context/Decision/Consequences/Alternatives) is complete (AC-Design); the two-axis model with change_target (10 values) and risk_surface (6 values) is documented in Decision §1 (AC-2AxisModel); BO-510 produces trait and TDD gating are explained in Decision §2 (AC-ProducesTrait); the (change_target, risk_surface) → mandatory-gate mapping table is present in Decision §3 (AC-MapTable); the Python computation in _build_agents_map and frontmatter materialisation are explained in Decision §4 (AC-Computation); ADR-001 self-hosting boundary is referenced and explained in Decision §5 (AC-SelfHosting); and the ADR is correctly numbered and written to docs/architecture/adrs/ADR-017-computed-quality-gates.md (AC-DecisionRecorded). No edits to the ADR were required.

### 2026-07-01 12:30 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  adr_sections_present: true
  ac_design_verified: true
  ac_2axismodel_verified: true
  ac_producestrait_verified: true
  ac_maptable_verified: true
  ac_computation_verified: true
  ac_selfhosting_verified: true
  ac_decisionrecorded_verified: true
  cross_references_resolve: true
  code_references_accurate: true
  style_consistent_with_existing_adrs: true
PR review passed. ADR-017 at docs/architecture/adrs/ADR-017-computed-quality-gates.md is correctly numbered (follows ADR-016), contains all required sections (Status/Context/Decision/Consequences/Alternatives), addresses all 7 ACs, and all cross-references resolve (ADR-001, ADR-007, build-ticket-workflow-dispatch.md, generate_ticket_from_ac.py, agent_registry.json, ticket-supervisor.md, building-epics SKILL.md). The description of _build_agents_map and its three module constants (_CANONICAL_SUPPORT_AGENTS, _SQL_AGENTS, _NOT_NEEDED_AGENTS) was verified against the actual source. No high or medium confidence findings. Zero suppressions.

### 2026-07-01 12:45 — commit (status: ok)
Auto-authorized commit gate: subject "docs: author ADR-017 computed quality gates design"; staged files: docs/architecture/adrs/ADR-017-computed-quality-gates.md tickets/00_inbox/epics/EPIC-ComputedQualityGates/.pending/adr_handoff.json tickets/00_inbox/epics/EPIC-ComputedQualityGates/01_adr_computed_quality_gates.md.
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed SHA e7d4fdff. Pre-commit hook `check-description-field` failed on first attempt (ADR missing description: frontmatter field); autofix applied (added description field), re-staged, and committed successfully on retry. 3 files, 322 insertions.

## Sign-offs
- [x] documentation-expert — 2026-07-01 12:15
- [x] adr-author — 2026-07-01 12:00
- [x] pr-reviewer — 2026-07-01 12:30
- [x] commit — 2026-07-01 12:45
- [ ] pull-request

## Implementation Tasks

### adr-author
- [x] Author ADR under docs/architecture/adrs/ADR-NNN-computed-quality-gates.md documenting the two-axis classification, guardrail-gates mapping table, and computation in Python

## Risk & Safety
- Touches money? No
- Touches data? No
- Reversibility? ADR is documentation only; fully reversible
