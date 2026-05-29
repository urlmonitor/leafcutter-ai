---
title: "Add default_artifact_checklist to test-writer"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_signoff_skill_manifest_section.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 02_03: Add default_artifact_checklist to test-writer

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/test-writer.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The test-writer agent (priority 5, role: quality) writes failing test stubs before coders implement. Its checklist should confirm stubs were created, all are red, and the red_baseline was captured.

Source of truth: `config/agent_registry.json` entry with `"id": "test-writer"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - test_stubs_created
  - all_tests_red
  - red_baseline_captured
```

## Acceptance Criteria
```gherkin
Given templates/agents/test-writer.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: test_stubs_created, all_tests_red, red_baseline_captured
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 10:00
- [x] pr-reviewer — 2026-05-29 10:05
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/test-writer.md` frontmatter: add `default_artifact_checklist: [test_stubs_created, all_tests_red, red_baseline_captured]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 10:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_efdbad1b
completion_manifest:
  frontmatter_checklist_added: true
  instruction_paragraph_added: true
Added `default_artifact_checklist: [test_stubs_created, all_tests_red, red_baseline_captured]` to `templates/agents/test-writer.md` frontmatter. Added "Completion Manifest (mandatory per signoff §2b)" instruction paragraph in the Sign-off section explaining each checklist item and referencing signoff §2b format rules.

### 2026-05-29 10:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_60fcd21e
completion_manifest:
  acceptance_criteria_satisfied: true
  no_regressions_found: true
  change_scope_matches_ticket: true
Frontmatter `default_artifact_checklist` contains exactly the three items specified by the ticket (`test_stubs_created`, `all_tests_red`, `red_baseline_captured`). Instruction paragraph correctly references signoff §2b, explains each item, and is additive only. Change approved.
