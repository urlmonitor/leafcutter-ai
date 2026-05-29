---
title: "Add default_artifact_checklist to reference-author"
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

# 02_18: Add default_artifact_checklist to reference-author

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/reference-author.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The reference-author agent (priority 10, role: documentation) produces lookup-oriented reference docs like API tables and schema dictionaries. Its checklist should confirm the reference doc was written, schema tables are complete, and the genre guard passed.

Source of truth: `config/agent_registry.json` entry with `"id": "reference-author"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - reference_doc_written
  - schema_tables_complete
  - genre_guard_passed
```

## Acceptance Criteria
```gherkin
Given templates/agents/reference-author.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: reference_doc_written, schema_tables_complete, genre_guard_passed
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 10:00
- [x] pr-reviewer — 2026-05-29 10:05
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/reference-author.md` frontmatter: add `default_artifact_checklist: [reference_doc_written, schema_tables_complete, genre_guard_passed]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 10:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_1ed8779d
completion_manifest:
  reference_doc_written: true
  schema_tables_complete: true
  genre_guard_passed: true
Added `default_artifact_checklist` to `templates/agents/reference-author.md` frontmatter with items `reference_doc_written`, `schema_tables_complete`, `genre_guard_passed`. Added `## Completion Manifest` instruction paragraph referencing signoff §2b.

### 2026-05-29 10:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_86866d68
completion_manifest:
  checklist_items_correct: true
  acceptance_criteria_met: true
  instruction_paragraph_references_signoff_s2b: true
Review passed. `default_artifact_checklist` contains exactly the three required items in correct order; the `## Completion Manifest` paragraph correctly references signoff §2b and includes the bare-false rule warning.
