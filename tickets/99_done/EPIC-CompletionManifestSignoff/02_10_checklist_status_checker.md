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
  documentation-expert: signed_off
  pr-reviewer: signed_off
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

- [x] documentation-expert — 2026-05-29 14:00
- [x] pr-reviewer — 2026-05-29 14:01
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/status-checker.md` frontmatter: add `default_artifact_checklist: [state_verified, git_history_checked, status_reported]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 14:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_73ae8d08
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Added `default_artifact_checklist: [state_verified, git_history_checked, status_reported]` to `templates/agents/status-checker.md` frontmatter. Added `## Completion Manifest (sign-off §2b)` instruction paragraph in the agent body explaining each checklist item and referencing `signoff` skill §2b for the full contract.

### 2026-05-29 14:01 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_1a007923
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
No high or medium findings. The `default_artifact_checklist` frontmatter (3 items) and §2b instruction paragraph are correctly formed and match the ticket's acceptance criteria exactly.
