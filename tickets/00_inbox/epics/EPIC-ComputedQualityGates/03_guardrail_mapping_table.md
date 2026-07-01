---
title: "Guardrail Mapping Table: (change_target, risk_surface) → agent gates"
status: in_progress
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
  python-coder: signed_off
  pr-reviewer: signed_off
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

- [x] AC-BO-620: config/guardrail_gates.yaml exists with (change_target, risk_surface) pairs mapping to agent lists
- [x] AC-BO-620-1: File structure is YAML with top-level key for each change_target (10 keys total)
- [x] AC-BO-620-2: Each change_target key maps to a dict with risk_surface keys (6 keys total)
- [x] AC-BO-620-3: Each (target, surface) pair maps to a list of mandatory agent names (strings)
- [x] AC-BO-620-4: File is loadable as valid YAML with no syntax errors
- [x] AC-BO-620-5: All agent names in the mapping are valid (cross-check against agent_registry.json or llm-expert audit)
- [x] AC-BO-620-1-i: Mapping table is populated with reasonable guardrail assignments (architect-review for schema changes, test-writer for code, documentation-expert for docs/prompt changes, etc.)

## Comments

### 2026-07-01 14:30 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  guardrail_gates_yaml_created: true
  all_10_change_targets_present: true
  all_6_risk_surfaces_per_target: true
  agent_names_validated_against_registry: true
  yaml_syntax_valid: true
  reasonable_guardrail_assignments: true
  file_staged: true
Created config/guardrail_gates.yaml with 10 change_target keys and 6 risk_surface keys each (60 pairs total). All agent names cross-checked against agent_registry.json is_ticket_phase:true entries; no invented names used. YAML validated via python3 yaml.safe_load. File staged. feedback script absent from worktree — using (submit-failed) fallback per §2a.

### 2026-07-01 15:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  yaml_valid: true
  targets_count: 10
  risk_surfaces_per_target: 6
  all_agent_names_valid: true
  reasonable_assignments: true
  staged_files_correct: true
All checks passed. guardrail_gates.yaml loads as valid YAML, contains exactly 10 change_target keys each with 6 risk_surface keys, all agent names are valid is_ticket_phase:true entries from agent_registry.json, assignments escalate appropriately for higher-risk surfaces (production/staging > integration > unit/none), and only config/guardrail_gates.yaml and the ticket appear in the staged diff. feedback script absent from worktree — using (submit-failed) fallback per §2a.

## Sign-offs
- [x] python-coder — 2026-07-01 14:30
- [x] pr-reviewer — 2026-07-01 15:00
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### python-coder
- [x] Create config/guardrail_gates.yaml with all 10 × 6 = 60 (change_target, risk_surface) pairs
- [x] Populate each pair with the appropriate list of mandatory agent gates
- [x] Document the file format and the mapping logic in the file header

## Risk & Safety
- Touches money? No
- Touches data? No
- Reversibility? Data file only; can be modified or removed
