---
title: "Update ticket format: numbered AC checklist, ac_coverage frontmatter, AC Coverage table"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_adr_contract_driven_acs.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/skills/ticket-authoring/SKILL.md
  - scripts/commit_guardian/commit_guardian.json
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 02: AC Format and Frontmatter

## Business Intent

Restructure the acceptance criteria format from Gherkin prose into a numbered
checklist that is both human-readable and machine-parseable, add `ac_coverage`
to frontmatter for hookable status gating, and introduce the AC Coverage table
for linking ACs to tests and implementations.

## Agent Contracts

### python-coder

- [x] AC-1: ticket-authoring SKILL.md body structure template updated — the "Acceptance Criteria" section shows the numbered checklist format `- [ ] AC-N: <description>` instead of Gherkin fenced block
- [x] AC-2: ticket-authoring SKILL.md includes an "Agent Contracts" alternative body structure for multi-agent tickets (per-agent AC blocks with Delivers to / Depends on)
- [x] AC-3: ticket-authoring SKILL.md frontmatter schema table includes `ac_coverage` as optional field (format: `N/M`, default: `0/M` where M = total AC count)
- [x] AC-4: ticket-authoring SKILL.md body structure includes "AC Coverage" table template with columns: AC, Test, Implementation, Validated
- [x] AC-5: commit_guardian.json ticket_frontmatter section accepts `ac_coverage` field (regex validation: `^\d+/\d+$`)
- [x] AC-6: ticket-authoring complete example updated to show new AC format (replaces Gherkin example)

## Sign-offs

- [x] test-writer — 2026-06-04 00:00
- [x] python-coder — 2026-06-04 00:05
- [x] test-runner — 2026-06-04 00:10
- [x] pr-reviewer — 2026-06-04 00:15
- [ ] commit
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies templates and hook config only.
- Reversibility? Fully reversible — the old Gherkin format still parses; this is additive.

## Comments

### 2026-06-04 00:00 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-04 00:05 — python-coder (status: ok)
feedback-id: fb_2026-06-04_6a750747
completion_manifest:
  AC-1_skill_body_updated: true
  AC-2_agent_contracts_alternative_added: true
  AC-3_ac_coverage_frontmatter_schema: true
  AC-4_ac_coverage_table_in_body: true
  AC-5_commit_guardian_ac_coverage_field: true
  AC-6_complete_example_updated: true
Updated ticket-authoring SKILL.md with numbered AC checklist format (AC-1–AC-4, AC-6) and added ac_coverage optional_fields entry to commit_guardian.json ticket_frontmatter section (AC-5). Also updated granularity rule and refinement checklist to remove Gherkin references.

### 2026-06-04 00:10 — test-runner (status: ok)
feedback-id: fb_2026-06-04_aa35b545
completion_manifest:
  tests_green: true
  no_contract_shrinking: true
All 45 commit_guardian unit tests pass. No Python code was changed, so contract-shrinking check is clean. JSON validity confirmed for commit_guardian.json.

### 2026-06-04 00:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_f32ec89a
completion_manifest:
  all_acs_met: true
  no_regressions: true
  json_valid: true
  changes_additive: true
All 6 ACs verified against the diff. ticket-authoring SKILL.md now uses numbered AC checklist format with AC Coverage table and Agent Contracts alternative. commit_guardian.json adds optional ac_coverage field with regex validation. 45 tests pass. Changes are fully additive and reversible.
