---
title: "Add default_artifact_checklist to commit"
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

# 02_08: Add default_artifact_checklist to commit

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/commit.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The commit agent (priority 12, role: commit) creates the git commit with precommit-autofix. Its checklist should confirm hooks passed, commit message is valid, and the ticket file is staged.

Source of truth: `config/agent_registry.json` entry with `"id": "commit"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - pre_commit_hooks_pass
  - commit_message_valid
  - ticket_staged
```

## Acceptance Criteria
```gherkin
Given templates/agents/commit.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: pre_commit_hooks_pass, commit_message_valid, ticket_staged
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/commit.md` frontmatter: add `default_artifact_checklist: [pre_commit_hooks_pass, commit_message_valid, ticket_staged]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
