---
title: "Add AC-checkbox recipe to signoff skill (shared foundation for all phase agents)"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 02_ac_format_and_frontmatter.md
  - 05_ac_validator_agent.md
priority: high
phase: "Phase 3"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/skills/signoff/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 07a: Signoff Skill — AC Checkbox Recipe

## Business Intent

All phase agents use the signoff skill. Adding the AC-checkbox recipe here
means every agent gets the behavior for free, and the recipe is defined once
rather than duplicated across 12 agent templates.

## Agent Contracts

### python-coder

- [ ] AC-1: signoff SKILL.md includes a new "§ AC Coverage Sign-Off" section that describes the per-AC checkbox protocol: detect `## Agent Contracts` section → find `### <my-agent-name>` block → flip `- [ ] AC-N:` to `- [x] AC-N:` → append `<!-- signed: <agent-name> -->`
- [ ] AC-2: The recipe includes the AC Coverage table fill protocol: find the row matching the AC-N → write evidence in the appropriate column (Implementation for coders/doc-writers, Test for test-writer)
- [ ] AC-3: The recipe includes a v1/v2 detection rule: if ticket body contains `## Agent Contracts`, use AC protocol; otherwise skip (backward compatible)
- [ ] AC-4: The recipe is documented as a sub-step of the existing sign-off flow — runs AFTER the agent completes its work and BEFORE the phase sign-off checkbox

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies skill doc only.
- Reversibility? Fully reversible — additive section in existing skill.
