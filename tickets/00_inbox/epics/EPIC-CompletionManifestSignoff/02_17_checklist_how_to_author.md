---
title: "Add default_artifact_checklist to how-to-author"
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

# 02_17: Add default_artifact_checklist to how-to-author

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/how-to-author.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The how-to-author agent (priority 10, role: documentation) writes task-oriented how-to guides. Its checklist should confirm the guide was written, placed in the correct location, and the steps are validated.

Source of truth: `config/agent_registry.json` entry with `"id": "how-to-author"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - guide_written
  - location_correct
  - steps_validated
```

## Acceptance Criteria
```gherkin
Given templates/agents/how-to-author.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: guide_written, location_correct, steps_validated
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/how-to-author.md` frontmatter: add `default_artifact_checklist: [guide_written, location_correct, steps_validated]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
