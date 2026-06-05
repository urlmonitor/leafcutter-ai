---
title: "AC tree splitting procedure and validation"
status: todo
components:
  - ac-store
created: 2026-06-05
depends_on:
  - 01_schema_validation.md
  - 06_ac_query_skill.md
priority: low
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/ac-tree-split/SKILL.md
  - unit_tests/skills/test_ac_tree_split.py
agents:
  test-writer: needed
  llm-expert: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/5
---

# 07: AC tree splitting procedure and validation

## Actor / Goal

In order to keep the AC store navigable as it grows, we need the ac-tree-split
skill to be tested and the split procedure validated end-to-end — so that when
agents encounter an overcrowded tree, they can follow a deterministic, tested
procedure to restructure it.

## Context

The ac-tree-split skill already exists as a prompt-based procedure in
templates/skills/ac-tree-split/SKILL.md. This ticket adds integration tests
that verify the split procedure works correctly: trigger detection, rewiring,
confirmation gates, audit trail, and post-split validation. It also dogfoods
the skill on ACS-100 (currently at 8 L1s, exceeding the hard cap).

## AC References

- Implements ACS-100h-1 (overcrowded parent triggers split)
- Implements ACS-100h-2 (rewires depends_on/covered_by without breakage)
- Implements ACS-100h-3 (user confirmation gates)
- Implements ACS-100h-4 (audit trail in amended_by + git)
- Implements ACS-100h-5 (post-split validation)

## Acceptance Criteria

- [ ] AC-1: check_ac_limits.py flags ACS-100 as overcrowded (8 > 7 L1s)
- [ ] AC-2: Split procedure applied to ACS-100 produces two valid L0s each with 3+ L1s
- [ ] AC-3: After split, no depends_on reference is dangling
- [ ] AC-4: After split, amended_by on every modified AC records the split operation
- [ ] AC-5: After split, check_ac_limits.py passes with no violations

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACS-100h-1 | | | |
| ACS-100h-2 | | | |
| ACS-100h-3 | | | |
| ACS-100h-4 | | | |
| ACS-100h-5 | | | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/skills/test_ac_tree_split.py
    covers: [ACS-100h-1, ACS-100h-2, ACS-100h-3, ACS-100h-4, ACS-100h-5]
    type: integration
    rationale: "Split is a multi-step procedure; integration tests verify end-to-end correctness"
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Write integration test that verifies ACS-100 triggers the limit
- [ ] Write test that simulates a horizontal split and validates rewiring
- [ ] Write test verifying amended_by audit trail is populated
- [ ] Write test verifying post-split validation passes
- [ ] Dogfood: execute the split on ACS-100 itself (manual, with user confirmation)
- [ ] Update SKILL.md with lessons learned from the dogfood

## Risk & Safety

- Touches money? No
- Touches data? Modifies AC YAML files (structural restructuring)
- Reversibility? Split is auditable via amended_by; can be manually reversed
