---
title: "Add default_artifact_checklist to sql-coder"
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

# 02_11: Add default_artifact_checklist to sql-coder

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/sql-coder.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The sql-coder agent (priority 7, role: coding) handles all SQL object creation. Its checklist should confirm SQL was deployed locally, tests pass, and naming conventions are met.

Source of truth: `config/agent_registry.json` entry with `"id": "sql-coder"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - sql_deployed_locally
  - sql_tests_passing
  - naming_conventions_met
```

## Acceptance Criteria
```gherkin
Given templates/agents/sql-coder.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: sql_deployed_locally, sql_tests_passing, naming_conventions_met
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/sql-coder.md` frontmatter: add `default_artifact_checklist: [sql_deployed_locally, sql_tests_passing, naming_conventions_met]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
