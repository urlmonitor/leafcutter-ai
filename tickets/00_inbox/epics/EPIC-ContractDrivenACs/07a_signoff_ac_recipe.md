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
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
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

- [x] AC-1: signoff SKILL.md includes a new "§ AC Coverage Sign-Off" section that describes the per-AC checkbox protocol: detect `## Agent Contracts` section → find `### <my-agent-name>` block → flip `- [ ] AC-N:` to `- [x] AC-N:` → append `<!-- signed: <agent-name> -->` <!-- signed: python-coder -->
- [x] AC-2: The recipe includes the AC Coverage table fill protocol: find the row matching the AC-N → write evidence in the appropriate column (Implementation for coders/doc-writers, Test for test-writer) <!-- signed: python-coder -->
- [x] AC-3: The recipe includes a v1/v2 detection rule: if ticket body contains `## Agent Contracts`, use AC protocol; otherwise skip (backward compatible) <!-- signed: python-coder -->
- [x] AC-4: The recipe is documented as a sub-step of the existing sign-off flow — runs AFTER the agent completes its work and BEFORE the phase sign-off checkbox <!-- signed: python-coder -->

## Sign-offs

- [x] python-coder — 2026-06-04 09:00
- [x] pr-reviewer — 2026-06-04 09:05
- [x] commit — 2026-06-04 09:10
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | Added §2c per-AC checkbox protocol section to signoff SKILL.md | ok — 2026-06-04 |
| AC-2 | | Added AC Coverage table fill protocol (§2c.3) with column mapping by agent role | ok — 2026-06-04 |
| AC-3 | | Added v1/v2 detection rule (§2c.1) in signoff SKILL.md | ok — 2026-06-04 |
| AC-4 | | Added §2c.4 positioning in sign-off flow (after work, before phase sign-off) | ok — 2026-06-04 |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies skill doc only.
- Reversibility? Fully reversible — additive section in existing skill.

## Comments

### 2026-06-04 09:00 — python-coder (status: ok)
feedback-id: fb_2026-06-04_58edfb28
completion_manifest:
  ac1_checkbox_protocol_added: true
  ac2_coverage_table_protocol_added: true
  ac3_v1v2_detection_rule_added: true
  ac4_flow_positioning_documented: true
Added §2c "AC Coverage Sign-Off" section to templates/skills/signoff/SKILL.md. Section covers §2c.1 v1/v2 detection rule, §2c.2 per-AC checkbox protocol, §2c.3 AC Coverage table fill protocol, and §2c.4 positioning in the sign-off flow. All four ACs satisfied.

### 2026-06-04 09:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_df5094f4
completion_manifest:
  ac1_satisfied: true
  ac2_satisfied: true
  ac3_satisfied: true
  ac4_satisfied: true
Reviewed §2c addition to signoff SKILL.md. All four ACs satisfied: per-AC checkbox protocol (§2c.2), AC Coverage table fill protocol (§2c.3), v1/v2 detection rule (§2c.1), and sign-off flow positioning (§2c.4) are all present and correct. No blockers.

### 2026-06-04 09:10 — commit (status: ok)
feedback-id: fb_2026-06-04_c50b419c
completion_manifest:
  files_staged_correctly: true
  commit_created: true
Staged templates/skills/signoff/SKILL.md and tickets/00_inbox/epics/EPIC-ContractDrivenACs/07a_signoff_ac_recipe.md. Committed §2c AC Coverage Sign-Off section addition to signoff SKILL.md on branch EPIC-ContractDrivenACs.
