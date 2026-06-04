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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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

- [ ] AC-1: ticket-authoring SKILL.md body structure template updated — the "Acceptance Criteria" section shows the numbered checklist format `- [ ] AC-N: <description>` instead of Gherkin fenced block
- [ ] AC-2: ticket-authoring SKILL.md includes an "Agent Contracts" alternative body structure for multi-agent tickets (per-agent AC blocks with Delivers to / Depends on)
- [ ] AC-3: ticket-authoring SKILL.md frontmatter schema table includes `ac_coverage` as optional field (format: `N/M`, default: `0/M` where M = total AC count)
- [ ] AC-4: ticket-authoring SKILL.md body structure includes "AC Coverage" table template with columns: AC, Test, Implementation, Validated
- [ ] AC-5: commit_guardian.json ticket_frontmatter section accepts `ac_coverage` field (regex validation: `^\d+/\d+$`)
- [ ] AC-6: ticket-authoring complete example updated to show new AC format (replaces Gherkin example)

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
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
| AC-5 | | | |
| AC-6 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies templates and hook config only.
- Reversibility? Fully reversible — the old Gherkin format still parses; this is additive.
