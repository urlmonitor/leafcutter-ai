---
title: "Add default_artifact_checklist to adr-author"
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

# 02_14: Add default_artifact_checklist to adr-author

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/adr-author.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The adr-author agent (priority 2, role: documentation) creates Architecture Decision Records. Its checklist should confirm the ADR file was created, all required sections are present, and the status field is set.

Source of truth: `config/agent_registry.json` entry with `"id": "adr-author"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - adr_file_created
  - all_sections_present
  - status_set
```

## Acceptance Criteria
```gherkin
Given templates/agents/adr-author.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: adr_file_created, all_sections_present, status_set
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/adr-author.md` frontmatter: add `default_artifact_checklist: [adr_file_created, all_sections_present, status_set]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
