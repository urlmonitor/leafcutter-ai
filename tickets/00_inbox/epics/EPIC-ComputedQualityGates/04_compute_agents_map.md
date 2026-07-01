---
title: "Compute + materialize agents map in Python; fix TDD bug"
status: todo
components:
  - infrastructure
created: 2026-07-01
depends_on:
  - 03_guardrail_mapping_table.md
priority: high
requires_adr: false
requires_diagram: false
files_touched:
  - scripts/ac_store/generate_ticket_from_ac.py
  - templates/skills/ticket-authoring/SKILL.md
  - templates/agents/ticket-supervisor.md
  - templates/skills/building-epics/SKILL.md
  - unit_tests/test_generate_ticket_from_ac.py
agents:
  python-coder: needed
  test-writer: needed
  test-runner: needed
  llm-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_traceability:
  - BO-560
  - BO-560-1
  - BO-560-2
  - BO-560-3
  - BO-560-1-i
  - BO-560-3-i
  - BO-530
  - BO-530-1
  - BO-530-2
  - BO-530-3
  - BO-530-1-i
  - BO-530-3-i
---

# 04: Compute + Materialize Agents Map (+ Fix TDD Bug)

## Goal

Extend generate_ticket_from_ac.py::_build_agents_map to compute the full ordered agent map from (change_target, risk_surface) + the work agent's produces trait via the guardrail table. Materialize it into ticket frontmatter. Auto-inject test-writer before + test-runner after any production_code agent. Fix the live TDD bug: emit a `## Test Requirements` block for code producers so test-writer doesn't self-skip. Reconcile the supervisor's skip prose so it doesn't undo the computed map.

## Context

AC-generated tickets currently fail TDD because:
1. generate_ticket_from_ac.py marks test-writer `needed` but emits no `## Test Requirements` block
2. The supervisor's skip rule fires (missing test_requirements.tests array) and test-writer auto-skips
3. Code ships without tests

The fix has three parts:

1. **Compute the agent map** from (change_target, risk_surface) → guardrails via config/guardrail_gates.yaml, union with the work agent's produces trait
2. **Materialize into frontmatter** with sign-off parity + enum guards satisfied; preserve explicit not_needed overrides
3. **Fix TDD bug**: Always emit a `## Test Requirements` block for production_code agents; reconcile the supervisor's skip prose (templates/agents/ticket-supervisor.md + templates/skills/building-epics/SKILL.md) so it doesn't silently undo the computed map

## Acceptance Criteria

- [ ] AC-BO-560: _build_agents_map computes the full ordered agent map from (change_target, risk_surface) + work agent's produces trait
- [ ] AC-BO-560-1: Reads config/guardrail_gates.yaml and looks up the (target, surface) pair to get mandatory guardrails
- [ ] AC-BO-560-2: Unions multi-value targets (e.g., both code + schema touches) to get all applicable guardrails
- [ ] AC-BO-560-3: Ordering is canonical (architect → test-writer → python-coder → sql-coder → test-runner → documentation-expert → pr-reviewer → commit → pull-request)
- [ ] AC-BO-560-1-i: Auto-injects test-writer before and test-runner after any agent marked as produces: production_code
- [ ] AC-BO-560-3-i: Preserves explicit not_needed overrides (does not recompute those to needed)
- [ ] AC-BO-530: TDD bug fixed — every AC-generated ticket for a production_code agent now has a `## Test Requirements` block
- [ ] AC-BO-530-1: _build_agents_map emits a default `## Test Requirements` block (even if empty tests array) for any ticket with a code producer
- [ ] AC-BO-530-2: test-writer can see the test_requirements field and does not self-skip for production_code tickets
- [ ] AC-BO-530-3: Supervisor skip prose (ticket-supervisor.md + building-epics/SKILL.md) is reconciled so it does not silently undo the computed agents map
- [ ] AC-BO-530-1-i: AC fulfillment gate validates that all code-producing tickets have non-zero test coverage or explicit risk acceptance
- [ ] AC-BO-530-3-i: Test suite covers the full agent-map computation (targt/surface pairs, union logic, ordering, test-writer injection, not_needed preservation)

## Comments

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] llm-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### python-coder
- [ ] Extend generate_ticket_from_ac.py::_build_agents_map to load config/guardrail_gates.yaml
- [ ] Implement (change_target, risk_surface) lookup and union logic for multi-value targets
- [ ] Implement canonical ordering of the agent map
- [ ] Auto-inject test-writer before + test-runner after any production_code agent
- [ ] Always emit `## Test Requirements` block for code producers (even if tests array is empty initially)
- [ ] Preserve explicit not_needed overrides in the computed map

### test-writer
- [ ] Add test_compute_agents_map_basic to unit_tests/test_generate_ticket_from_ac.py (single target/surface pair)
- [ ] Add test_compute_agents_map_union to unit_tests/test_generate_ticket_from_ac.py (multi-value targets union their gates)
- [ ] Add test_canonical_ordering to unit_tests/test_generate_ticket_from_ac.py (verify order matches canonical)
- [ ] Add test_test_writer_injection to unit_tests/test_generate_ticket_from_ac.py (test-writer injected before code producers)
- [ ] Add test_test_runner_injection to unit_tests/test_generate_ticket_from_ac.py (test-runner injected after code producers)
- [ ] Add test_preserve_not_needed to unit_tests/test_generate_ticket_from_ac.py (explicit not_needed is never recomputed)
- [ ] Add test_tdd_bug_fix to unit_tests/test_generate_ticket_from_ac.py (verify ## Test Requirements block is emitted for code producers)

### llm-expert
- [ ] Review and reconcile supervisor skip prose in templates/agents/ticket-supervisor.md (ensure it does not auto-skip test-writer for computed agents)
- [ ] Review and reconcile skill prose in templates/skills/building-epics/SKILL.md (ensure it documents the computed map, not overriding it)

## Risk & Safety
- Touches money? No
- Touches data? No
- Reversibility? Python computation is deterministic; can be disabled by reverting to stub agent map if needed
