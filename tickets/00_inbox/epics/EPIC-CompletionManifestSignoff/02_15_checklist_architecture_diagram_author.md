---
title: "Add default_artifact_checklist to architecture-diagram-author"
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

# 02_15: Add default_artifact_checklist to architecture-diagram-author

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/architecture-diagram-author.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The architecture-diagram-author agent (priority 3, role: documentation) creates C4 mermaid diagrams. Its checklist should confirm the diagram was created, the flight level selection is correct, and cross-links are added.

Source of truth: `config/agent_registry.json` entry with `"id": "architecture-diagram-author"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - diagram_created
  - flight_level_correct
  - cross_links_added
```

## Acceptance Criteria
```gherkin
Given templates/agents/architecture-diagram-author.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: diagram_created, flight_level_correct, cross_links_added
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/architecture-diagram-author.md` frontmatter: add `default_artifact_checklist: [diagram_created, flight_level_correct, cross_links_added]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
