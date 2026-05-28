---
title: "Add default_artifact_checklist to pull-request"
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

# 02_09: Add default_artifact_checklist to pull-request

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/pull-request.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The pull-request agent (priority 13, role: commit) pushes the branch and opens the PR. Its checklist should confirm the branch was pushed, PR was created, and the PR body is complete.

Source of truth: `config/agent_registry.json` entry with `"id": "pull-request"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - branch_pushed
  - pr_created
  - pr_body_complete
```

## Acceptance Criteria
```gherkin
Given templates/agents/pull-request.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: branch_pushed, pr_created, pr_body_complete
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/pull-request.md` frontmatter: add `default_artifact_checklist: [branch_pushed, pr_created, pr_body_complete]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
