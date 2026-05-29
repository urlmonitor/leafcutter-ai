---
title: "Add default_artifact_checklist to python-coder"
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

# 02_02: Add default_artifact_checklist to python-coder

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/python-coder.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The python-coder agent (priority 6, role: coding) is the primary implementation agent. Its checklist should confirm code was written, tests pass, doc-enforcer is clean, and complexity checks pass.

Source of truth: `config/agent_registry.json` entry with `"id": "python-coder"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - code_implemented
  - tests_passing
  - doc_enforcer_clean
  - complexity_check_clean
```

## Acceptance Criteria
```gherkin
Given templates/agents/python-coder.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: code_implemented, tests_passing, doc_enforcer_clean, complexity_check_clean
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 10:00
- [x] pr-reviewer — 2026-05-29 10:05
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/python-coder.md` frontmatter: add `default_artifact_checklist: [code_implemented, tests_passing, doc_enforcer_clean, complexity_check_clean]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 10:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_12578f1c
completion_manifest:
  frontmatter_checklist_added: true
  instruction_paragraph_added: true
Added `default_artifact_checklist` to `templates/agents/python-coder.md` frontmatter with four items: code_implemented, tests_passing, doc_enforcer_clean, complexity_check_clean. Added a "Completion Manifest (mandatory)" instruction subsection under Sign-off referencing signoff §2b format rules.

### 2026-05-29 10:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_85cb77f3
completion_manifest:
  acceptance_criteria_verified: true
  no_regressions_found: true
  diff_matches_ticket_spec: true
Reviewed diff: frontmatter checklist contains exactly the four specified items; instruction paragraph correctly references signoff §2b and is placed logically. Acceptance criteria pass. Approved for commit.
