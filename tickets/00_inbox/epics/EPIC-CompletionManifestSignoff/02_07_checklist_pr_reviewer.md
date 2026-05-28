---
title: "Add default_artifact_checklist to pr-reviewer"
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

# 02_07: Add default_artifact_checklist to pr-reviewer

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/pr-reviewer.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The pr-reviewer agent (priority 11, role: review) is the final quality gate before commit. Its checklist should confirm the diff was fully reviewed, no high-severity findings remain, and scope is verified.

Source of truth: `config/agent_registry.json` entry with `"id": "pr-reviewer"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - diff_reviewed
  - no_high_findings
  - scope_verified
```

## Acceptance Criteria
```gherkin
Given templates/agents/pr-reviewer.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: diff_reviewed, no_high_findings, scope_verified
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/pr-reviewer.md` frontmatter: add `default_artifact_checklist: [diff_reviewed, no_high_findings, scope_verified]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
