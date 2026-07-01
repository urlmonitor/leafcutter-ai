---
title: "Test constraints + complexity-driven model tier selection"
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
  - scripts/ac_store/generate_ticket_from_ac.py
  - templates/agents/test-writer.md
  - templates/agents/llm-expert.md
  - templates/skills/ticket-authoring/SKILL.md
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
  - BO-550
  - BO-550-1
  - BO-550-2
  - BO-550-1-i
  - BO-630
  - BO-630-1
  - BO-630-2
  - BO-630-1-i
  - BO-640
  - BO-640-1
  - BO-640-2
  - BO-640-3
  - BO-640-1-i
---

# 06: Test Constraints + Complexity-Driven Model Tier Selection

## Goal

Add a `test_constraints` frontmatter field that test-writer honors (e.g., "unit tests only, no integration tests" or "integration tests required"). Implement complexity-driven model tier selection: low/medium complexity tasks use Sonnet, high complexity escalates to Opus with a "can you simplify?" challenge gate before the escalation.

## Context

Not all tests need the same level of coverage or isolation. Some tickets require integration tests, others must avoid them. The `test_constraints` field lets the author specify test requirements that test-writer respects.

Complexity also drives model selection. Simple tickets run fine on Sonnet (cheaper, faster); complex ones may need Opus reasoning. A challenge gate asks "can this be simplified?" before escalating to Opus, avoiding unnecessary cost.

## Acceptance Criteria

- [ ] AC-BO-550: test_constraints frontmatter field added to ticket schema (optional, string or list of strings)
- [ ] AC-BO-550-1: test-writer reads test_constraints and honors constraints (e.g., "no integration tests" → only unit test suggestions)
- [ ] AC-BO-550-2: test_constraints examples documented in SKILL.md (unit_only, integration_required, no_db_tests, etc.)
- [ ] AC-BO-550-1-i: Test suite validates test_constraints field is parsed and honored
- [ ] AC-BO-630: complexity field added to ticket frontmatter (optional, enum: low / medium / high)
- [ ] AC-BO-630-1: generate_ticket_from_ac.py infers complexity from AC characteristics (number of ACs, change scope, blast radius)
- [ ] AC-BO-630-2: complexity → model_tier mapping: low/medium → Sonnet, high → challenge gate before Opus
- [ ] AC-BO-630-1-i: Test suite validates complexity inference logic
- [ ] AC-BO-640: challenge-gate prose added to llm-expert template (when complexity: high, ask "can you simplify?")
- [ ] AC-BO-640-1: Challenge gate captures user response and either scales back the ticket scope or escalates to Opus
- [ ] AC-BO-640-2: Documentation in SKILL.md explains complexity-driven tier selection and challenge gate
- [ ] AC-BO-640-3: Challenge gate is optional (user can override with complexity_override: force_opus if needed)
- [ ] AC-BO-640-1-i: Test suite validates challenge gate flow (user says "yes simplify" → scope reduced, user says "no, need Opus" → escalates)

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
- [ ] Add test_constraints field to ticket frontmatter schema (templates/skills/ticket-authoring/SKILL.md)
- [ ] Add complexity field to ticket frontmatter schema (optional, enum: low / medium / high)
- [ ] Extend generate_ticket_from_ac.py to infer complexity from AC characteristics
- [ ] Implement complexity → model_tier mapping (low/medium → haiku/sonnet, high → opus)

### test-writer
- [ ] Update test-writer.md template to read and honor test_constraints field
- [ ] Add logic to skip integration-test suggestions if test_constraints contains "no integration"

### llm-expert
- [ ] Add challenge-gate prose to llm-expert.md for complexity: high tickets ("Can you simplify this ticket scope to run on Sonnet?")
- [ ] Implement response handling: user simplifies → reduce scope; user declines → escalate to Opus
- [ ] Add complexity override mechanism (complexity_override: force_opus)
- [ ] Document challenge gate and complexity-driven tier selection in SKILL.md

### test-writer
- [ ] Add test_test_constraints_parsing to unit_tests/test_generate_ticket_from_ac.py
- [ ] Add test_complexity_inference to unit_tests/test_generate_ticket_from_ac.py
- [ ] Add test_complexity_to_tier_mapping to unit_tests/test_generate_ticket_from_ac.py
- [ ] Add test_challenge_gate_flow to unit_tests/test_generate_ticket_from_ac.py (simplify vs escalate paths)

## Risk & Safety
- Touches money? Potentially (Opus usage is more expensive than Sonnet; challenge gate reduces costs)
- Touches data? No
- Reversibility? Fields are optional; can be omitted or removed without breaking existing tickets
