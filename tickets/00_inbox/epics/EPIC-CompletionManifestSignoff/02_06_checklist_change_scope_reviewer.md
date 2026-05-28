---
title: "Add default_artifact_checklist to change-scope-reviewer"
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

# 02_06: Add default_artifact_checklist to change-scope-reviewer

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/change-scope-reviewer.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The change-scope-reviewer agent (priority 10, role: review) verifies that the actual diff matches the planned scope. Its checklist should confirm the diff was reviewed, all files were classified, and no hard scope violations exist.

Source of truth: `config/agent_registry.json` entry with `"id": "change-scope-reviewer"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - diff_reviewed
  - scope_classification_complete
  - no_hard_violations
```

## Acceptance Criteria
```gherkin
Given templates/agents/change-scope-reviewer.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: diff_reviewed, scope_classification_complete, no_hard_violations
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/change-scope-reviewer.md` frontmatter: add `default_artifact_checklist: [diff_reviewed, scope_classification_complete, no_hard_violations]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
