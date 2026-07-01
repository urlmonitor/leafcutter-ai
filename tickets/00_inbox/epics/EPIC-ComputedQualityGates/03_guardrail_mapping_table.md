---
title: "Guardrail Mapping Table: (change_target, risk_surface) → agent gates"
status: todo
components:
  - infrastructure
created: 2026-07-01
depends_on:
  - 02_change_classification_frontmatter.md
priority: high
requires_adr: false
requires_diagram: false
files_touched:
  - config/guardrail_gates.yaml
agents:
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_traceability:
  - BO-620
  - BO-620-1
  - BO-620-2
  - BO-620-3
  - BO-620-4
  - BO-620-5
  - BO-620-1-i
---

# 03: Guardrail Mapping Table

## Goal

Create a machine-readable data file mapping each (change_target, risk_surface) pair to its mandatory guardrail agents. Each pair maps to a list of agent names (e.g., architect-review, test-writer) that must be included in the computed agent map.

## Context

The agent map computation in ticket generation needs a lookup table: given a change's classification (target + surface), which agents are mandatory? This file drives the deterministic computation. Multi-value targets (e.g., a change that touches both code and schema) union their gates.

The file format is YAML and lives at config/guardrail_gates.yaml. It is read by generate_ticket_from_ac.py::_build_agents_map to compute the full agent map.

## Acceptance Criteria

- [ ] AC-BO-620: config/guardrail_gates.yaml exists with (change_target, risk_surface) pairs mapping to agent lists
- [ ] AC-BO-620-1: File structure is YAML with top-level key for each change_target (10 keys total)
- [ ] AC-BO-620-2: Each change_target key maps to a dict with risk_surface keys (6 keys total)
- [ ] AC-BO-620-3: Each (target, surface) pair maps to a list of mandatory agent names (strings)
- [ ] AC-BO-620-4: File is loadable as valid YAML with no syntax errors
- [ ] AC-BO-620-5: All agent names in the mapping are valid (cross-check against agent_registry.json or llm-expert audit)
- [ ] AC-BO-620-1-i: Mapping table is populated with reasonable guardrail assignments (architect-review for schema changes, test-writer for code, documentation-expert for docs/prompt changes, etc.)

## Comments

## Sign-offs
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### python-coder
- [ ] Create config/guardrail_gates.yaml with all 10 × 6 = 60 (change_target, risk_surface) pairs
- [ ] Populate each pair with the appropriate list of mandatory agent gates
- [ ] Document the file format and the mapping logic in the file header

## Risk & Safety
- Touches money? No
- Touches data? No
- Reversibility? Data file only; can be modified or removed
