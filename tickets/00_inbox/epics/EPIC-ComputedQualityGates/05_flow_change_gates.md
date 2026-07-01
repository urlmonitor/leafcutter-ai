---
title: "Flow-change gates: architect + docs before coder"
status: todo
components:
  - infrastructure
created: 2026-07-01
depends_on:
  - 04_compute_agents_map.md
priority: high
requires_adr: false
requires_diagram: false
files_touched:
  - config/guardrail_gates.yaml
  - templates/agents/ticket-supervisor.md
  - templates/skills/building-epics/SKILL.md
agents:
  llm-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_traceability:
  - BO-540
  - BO-540-1
  - BO-540-2
  - BO-540-1-i
---

# 05: Flow-Change Gates (Architect + Docs Before Coder)

## Goal

When the classification implies a structural/flow change (certain change_target + risk_surface combinations), inject architect-review + documentation-expert BEFORE any coder in the computed agent chain. This ensures design review and doc planning happen before implementation.

## Context

Some changes are architectural decisions that require design review and documentation planning before code is written. The guardrail table should flag these (e.g., changes to infrastructure or pipeline targets with contract_boundary or safety surfaces) and ensure architect-review and documentation-expert are sequenced before python-coder / sql-coder.

The ticket-supervisor and building-epics skill need to respect this ordering so the phase agents run in the correct sequence.

## Acceptance Criteria

- [ ] AC-BO-540: config/guardrail_gates.yaml marks certain (change_target, risk_surface) pairs as flow-change requiring architect + docs before code
- [ ] AC-BO-540-1: Flow-change pairs are identified (e.g., infrastructure or pipeline targets with contract_boundary or safety surfaces)
- [ ] AC-BO-540-2: The computed agent map sequences architect-review + documentation-expert BEFORE python-coder / sql-coder for flow-change pairs
- [ ] AC-BO-540-1-i: Ticket-supervisor and building-epics skill properly sequence the agents so design/docs phases run before code phase

## Comments

## Sign-offs
- [ ] llm-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### llm-expert
- [ ] Update config/guardrail_gates.yaml to mark flow-change pairs (architect + docs mandatory before coders)
- [ ] Review ticket-supervisor.md to ensure flow-change ordering is preserved
- [ ] Review building-epics/SKILL.md to ensure flow-change ordering is preserved across the epic

## Risk & Safety
- Touches money? No
- Touches data? No
- Reversibility? Guardrail table modifications are data-only; can be reverted
