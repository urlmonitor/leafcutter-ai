---
title: "Add default_artifact_checklist to architect-review"
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
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02_01: Add default_artifact_checklist to architect-review

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/architect-review.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The architect-review agent (priority 4, role: review) runs early in the ticket lifecycle to assess structural impact. Its checklist should confirm it performed blast-radius analysis, classified impact, and produced the required architectural note.

Source of truth: `config/agent_registry.json` entry with `"id": "architect-review"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - blast_radius_assessed
  - impact_classified
  - architectural_note_written
```

## Acceptance Criteria
```gherkin
Given templates/agents/architect-review.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: blast_radius_assessed, impact_classified, architectural_note_written
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 13:30
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/architect-review.md` frontmatter: add `default_artifact_checklist: [blast_radius_assessed, impact_classified, architectural_note_written]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 13:30 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_dad7c0bd
completion_manifest:
  frontmatter_checklist_added: true
  body_instruction_paragraph_added: true
Added `default_artifact_checklist: [blast_radius_assessed, impact_classified, architectural_note_written]` to `templates/agents/architect-review.md` frontmatter and inserted a "Sign-off Completion Manifest" section in the body referencing `signoff` §2b with per-item guidance and bare-false rule reminder.
