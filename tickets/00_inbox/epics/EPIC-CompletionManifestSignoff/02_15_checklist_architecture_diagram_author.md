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
  documentation-expert: signed_off
  pr-reviewer: signed_off
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

- [x] documentation-expert — 2026-05-29 00:00
- [x] pr-reviewer — 2026-05-29 00:01
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/architecture-diagram-author.md` frontmatter: add `default_artifact_checklist: [diagram_created, flight_level_correct, cross_links_added]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 00:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_d3dc4d1c
completion_manifest:
  frontmatter_checklist_added: true
  instruction_paragraph_added: true
Added `default_artifact_checklist: [diagram_created, flight_level_correct, cross_links_added]` to `templates/agents/architecture-diagram-author.md` frontmatter. Added a "Completion Manifest (mandatory on sign-off)" section to the agent body referencing `signoff` §2b and the bare-false rule.

### 2026-05-29 00:01 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_7e69de7b
completion_manifest:
  acceptance_criteria_met: true
  no_regressions: true
  frontmatter_valid: true
Frontmatter `default_artifact_checklist` key present with exactly the three required items (diagram_created, flight_level_correct, cross_links_added). Instruction paragraph correctly references signoff §2b and the bare-false rule. Acceptance criteria fully satisfied. No regressions detected.
