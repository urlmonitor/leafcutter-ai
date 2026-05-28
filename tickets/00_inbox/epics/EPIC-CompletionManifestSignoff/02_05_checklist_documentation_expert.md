---
title: "Add default_artifact_checklist to documentation-expert"
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

# 02_05: Add default_artifact_checklist to documentation-expert

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/documentation-expert.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The documentation-expert agent (priority 10, role: documentation) is the Diataxis-routing orchestrator. Its checklist should confirm a doc was written, cross-links are correct, and the genre classification is appropriate.

Source of truth: `config/agent_registry.json` entry with `"id": "documentation-expert"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - doc_written
  - cross_links_added
  - diataxis_genre_correct
```

## Acceptance Criteria
```gherkin
Given templates/agents/documentation-expert.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: doc_written, cross_links_added, diataxis_genre_correct
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/documentation-expert.md` frontmatter: add `default_artifact_checklist: [doc_written, cross_links_added, diataxis_genre_correct]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
