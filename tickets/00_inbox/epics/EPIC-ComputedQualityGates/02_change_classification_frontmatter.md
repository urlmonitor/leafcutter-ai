---
title: "Add change_target + risk_surface frontmatter fields + guard"
status: todo
components:
  - infrastructure
created: 2026-07-01
depends_on:
  - 01_adr_computed_quality_gates.md
priority: high
requires_adr: false
requires_diagram: false
files_touched:
  - templates/skills/ticket-authoring/SKILL.md
  - scripts/ticket_frontmatter_guard.py
  - unit_tests/test_ticket_frontmatter_guard.py
agents:
  python-coder: needed
  test-writer: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_traceability:
  - BO-610
  - BO-610-1
  - BO-610-2
  - BO-610-3
  - BO-610-4
  - BO-610-5
  - BO-610-3-i
  - BO-610-4-i
---

# 02: Change Classification Frontmatter Fields + Guard

## Goal

Add `change_target` (10-value enum) and `risk_surface` (6-value enum) fields to the ticket frontmatter schema. Extend the ticket_frontmatter_guard hook to validate both fields are present and hold valid enum values.

## Context

The computed quality gates system uses a two-axis classification:

- **change_target** (what the change touches): code, schema, ui, infrastructure, pipeline, prompt, model, config, docs, dependency
- **risk_surface** (where the blast radius lands): internal, contract_boundary, auth, privacy, safety, cost

Every ticket must declare its axes so the agent map can be computed during generation. The guard validates these fields in all new tickets.

## Acceptance Criteria

- [ ] AC-BO-610: change_target and risk_surface fields added to ticket frontmatter schema (SKILL.md)
- [ ] AC-BO-610-1: change_target enum has 10 valid values (code, schema, ui, infrastructure, pipeline, prompt, model, config, docs, dependency)
- [ ] AC-BO-610-2: risk_surface enum has 6 valid values (internal, contract_boundary, auth, privacy, safety, cost)
- [ ] AC-BO-610-3: ticket_frontmatter_guard validates change_target is present and one of the 10 values; blocks write if invalid or absent
- [ ] AC-BO-610-4: ticket_frontmatter_guard validates risk_surface is present and one of the 6 values; blocks write if invalid or absent
- [ ] AC-BO-610-3-i: Guard test covers all 10 change_target values (both valid and invalid)
- [ ] AC-BO-610-4-i: Guard test covers all 6 risk_surface values (both valid and invalid)

## Comments

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### python-coder
- [ ] Add change_target and risk_surface fields to the frontmatter schema in templates/skills/ticket-authoring/SKILL.md
- [ ] Extend scripts/ticket_frontmatter_guard.py to validate change_target enum (10 values)
- [ ] Extend scripts/ticket_frontmatter_guard.py to validate risk_surface enum (6 values)

### test-writer
- [ ] Add test_change_target_validation to unit_tests/test_ticket_frontmatter_guard.py covering all 10 valid values + invalid cases
- [ ] Add test_risk_surface_validation to unit_tests/test_ticket_frontmatter_guard.py covering all 6 valid values + invalid cases

## Risk & Safety
- Touches money? No
- Touches data? No
- Reversibility? Frontmatter fields are optional if kept optional; guard can be removed
