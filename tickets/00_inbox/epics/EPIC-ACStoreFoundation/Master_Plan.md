---
title: "EPIC: AC Store Foundation — Schema Enforcement and Structural Integrity"
type: epic
status: todo
components:
  - ac-store
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: AC Store Foundation — Schema Enforcement and Structural Integrity

## Problem

The AC store has 100+ structured requirements but its enforcement layer is
incomplete. Only two L2 ACs are implemented and tested (ACS-100c-1, ACS-100c-2
— tree branching limits). The remaining 30 L2 behaviors — schema validation,
folder structure enforcement, ownership rules, authorship tracking, query
capabilities, and tree splitting — exist as specs but have no implementation.

Without these, the AC store is a convention enforced by agent prompts rather
than a system enforced by tooling. Agents can create malformed ACs, duplicate
IDs, orphaned references, and structurally invalid trees without detection.

## Goal

After this epic lands:

- Every AC YAML file is validated against the full schema at commit time
- Feature folders follow deterministic naming conventions (machine-verifiable)
- Flight-level ownership rules are enforced (PO writes L0/L1, BA writes L2/L3)
- Authorship identity is tracked and configurable per agent/skill
- Pipeline agents can query the AC store programmatically (by level, parent, component)
- Overcrowded AC trees can be split via a guided prompt-based procedure

## Scope

Seven sub-tickets, grouped by L1 parent. Each ticket implements all L2s under
one L1 (schema validation, folder structure, ownership, tracking, identity,
query, splitting).

| # | File | L1 Parent | L2 Count | Agent | Status |
|---|------|-----------|----------|-------|--------|
| 01 | [01_schema_validation.md](./01_schema_validation.md) | ACS-100a | 6 | python-coder | `[ ]` |
| 02 | [02_folder_structure.md](./02_folder_structure.md) | ACS-100b | 5 | python-coder | `[ ]` |
| 03 | [03_level_ownership.md](./03_level_ownership.md) | ACS-100c | 3 | python-coder | `[ ]` |
| 04 | [04_authorship_tracking.md](./04_authorship_tracking.md) | ACS-100d | 4 | python-coder | `[ ]` |
| 05 | [05_configurable_identity.md](./05_configurable_identity.md) | ACS-100e | 4 | python-coder | `[ ]` |
| 06 | [06_ac_query_skill.md](./06_ac_query_skill.md) | ACS-100f | 5 | python-coder | `[ ]` |
| 07 | [07_tree_splitting.md](./07_tree_splitting.md) | ACS-100h | 5 | llm-expert | `[ ]` |

## Dependency Graph

```
01_schema_validation (foundation — others depend on valid schema)
├── 02_folder_structure (needs schema validator to confirm ID formats)
├── 03_level_ownership (needs schema to distinguish L0/L1/L2)
├── 04_authorship_tracking (needs schema fields: origin_agent, amended_by)
│   └── 05_configurable_identity (extends authorship with defaults)
├── 06_ac_query_skill (reads validated AC files)
└── 07_tree_splitting (uses query + validator to detect and fix overcrowding)
```

## AC References

This epic implements:
- ACS-100a-1 through ACS-100a-6 (schema validation)
- ACS-100b-1 through ACS-100b-5 (folder structure)
- ACS-100c-3 through ACS-100c-5 (level ownership)
- ACS-100d-1 through ACS-100d-4 (authorship tracking)
- ACS-100e-1 through ACS-100e-4 (configurable identity)
- ACS-100f-1 through ACS-100f-5 (AC query skill)
- ACS-100h-1 through ACS-100h-5 (tree splitting)

## Exit Criteria

- All 30 L2 ACs have `work_status: done`, `covered_by` populated, `implemented_by` populated
- `build-self.sh` passes with no errors
- All new tests pass in CI
- The ac-tree-split skill is dogfooded on ACS-100 itself (it currently has 8 L1s)
