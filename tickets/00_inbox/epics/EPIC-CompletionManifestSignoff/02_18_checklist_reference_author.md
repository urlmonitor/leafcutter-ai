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
  documentation-expert: needed
  pr-reviewer: needed
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

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/reference-author.md` frontmatter: add `default_artifact_checklist: [reference_doc_written, schema_tables_complete, genre_guard_passed]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
