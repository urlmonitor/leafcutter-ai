---
title: "Add default_artifact_checklist to pull-request"
status: done
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
  commit: signed_off
  pull-request: not_needed
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

- [x] documentation-expert — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:05
- [x] commit — 2026-05-29 12:12

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/pull-request.md` frontmatter: add `default_artifact_checklist: [branch_pushed, pr_created, pr_body_complete]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_f0738b5a
Added `default_artifact_checklist: [branch_pushed, pr_created, pr_body_complete]` to `templates/agents/pull-request.md` frontmatter. Added Completion Manifest section in the body referencing signoff §2b `completion_manifest:` schema and placement rules.

### 2026-05-29 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_70aa90b8
All acceptance criteria met: `default_artifact_checklist` key present as YAML list with exactly `branch_pushed`, `pr_created`, `pr_body_complete`. Completion Manifest paragraph added correctly referencing signoff §2b. No regressions to existing agent behavior.

### 2026-05-29 12:12 — commit (status: ok)
feedback-id: fb_2026-05-29_c6d99f06
Committed `templates/agents/pull-request.md` with `default_artifact_checklist` frontmatter and Completion Manifest instruction paragraph. Staged explicit paths only: `templates/agents/pull-request.md` and ticket file.
