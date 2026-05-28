---
title: "Add default_artifact_checklist to status-checker"
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

# 02_10: Add default_artifact_checklist to status-checker

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/status-checker.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The status-checker agent (priority 1, role: analysis) verifies system state before other agents proceed. Its checklist should confirm state was verified, git history was checked, and status was reported.

Source of truth: `config/agent_registry.json` entry with `"id": "status-checker"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - state_verified
  - git_history_checked
  - status_reported
```

## Acceptance Criteria
```gherkin
Given templates/agents/status-checker.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: state_verified, git_history_checked, status_reported
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/status-checker.md` frontmatter: add `default_artifact_checklist: [state_verified, git_history_checked, status_reported]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
