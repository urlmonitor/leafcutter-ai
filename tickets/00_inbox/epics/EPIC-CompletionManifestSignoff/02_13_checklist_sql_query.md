---
title: "Add default_artifact_checklist to sql-query"
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

# 02_13: Add default_artifact_checklist to sql-query

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/sql-query.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The sql-query agent (priority 7, role: coding) authors ad-hoc SQL queries for analysis/debugging. Its checklist should confirm the query was authored, reviewed for correctness, and past queries were consulted.

Source of truth: `config/agent_registry.json` entry with `"id": "sql-query"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - query_authored
  - query_reviewed
  - past_queries_checked
```

## Acceptance Criteria
```gherkin
Given templates/agents/sql-query.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: query_authored, query_reviewed, past_queries_checked
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/sql-query.md` frontmatter: add `default_artifact_checklist: [query_authored, query_reviewed, past_queries_checked]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
