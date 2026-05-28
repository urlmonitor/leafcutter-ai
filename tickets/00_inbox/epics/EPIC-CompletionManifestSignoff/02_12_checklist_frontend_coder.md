---
title: "Add default_artifact_checklist to frontend-coder"
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
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02_12: Add default_artifact_checklist to frontend-coder

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/frontend-coder.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The frontend-coder agent (priority 8, role: coding) handles UI component creation. Its checklist should confirm code was implemented, UI was visually verified, and design principles were applied.

Source of truth: `config/agent_registry.json` entry with `"id": "frontend-coder"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - code_implemented
  - ui_verified
  - design_principles_applied
```

## Acceptance Criteria
```gherkin
Given templates/agents/frontend-coder.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: code_implemented, ui_verified, design_principles_applied
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/frontend-coder.md` frontmatter: add `default_artifact_checklist: [code_implemented, ui_verified, design_principles_applied]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
