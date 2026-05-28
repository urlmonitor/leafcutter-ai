---
title: "Add default_artifact_checklist to user-surface-smoker"
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

# 02_19: Add default_artifact_checklist to user-surface-smoker

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/user-surface-smoker.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The user-surface-smoker agent (priority 11.5, role: quality) invokes user-facing surfaces end-to-end and asserts observable side-effects. Its checklist should confirm the surface was invoked, assertions passed, and no placeholder signatures were detected.

Source of truth: `config/agent_registry.json` entry with `"id": "user-surface-smoker"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - surface_invoked
  - assertions_passed
  - no_placeholder_signatures
```

## Acceptance Criteria
```gherkin
Given templates/agents/user-surface-smoker.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: surface_invoked, assertions_passed, no_placeholder_signatures
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/user-surface-smoker.md` frontmatter: add `default_artifact_checklist: [surface_invoked, assertions_passed, no_placeholder_signatures]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
