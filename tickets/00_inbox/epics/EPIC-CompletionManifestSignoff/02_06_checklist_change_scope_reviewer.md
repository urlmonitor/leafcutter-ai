---
title: "Add default_artifact_checklist to change-scope-reviewer"
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
  commit: signed_off
  pull-request: needed
---

# 02_06: Add default_artifact_checklist to change-scope-reviewer

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/change-scope-reviewer.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The change-scope-reviewer agent (priority 10, role: review) verifies that the actual diff matches the planned scope. Its checklist should confirm the diff was reviewed, all files were classified, and no hard scope violations exist.

Source of truth: `config/agent_registry.json` entry with `"id": "change-scope-reviewer"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - diff_reviewed
  - scope_classification_complete
  - no_hard_violations
```

## Acceptance Criteria
```gherkin
Given templates/agents/change-scope-reviewer.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: diff_reviewed, scope_classification_complete, no_hard_violations
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 00:00
- [x] pr-reviewer — 2026-05-29 00:01
- [x] commit — 2026-05-29 00:02
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/change-scope-reviewer.md` frontmatter: add `default_artifact_checklist: [diff_reviewed, scope_classification_complete, no_hard_violations]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 00:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_4edddc43
completion_manifest:
  frontmatter_checklist_added: true
  instruction_paragraph_added: true
Added `default_artifact_checklist` to `templates/agents/change-scope-reviewer.md` frontmatter with items `diff_reviewed`, `scope_classification_complete`, `no_hard_violations`. Added instruction paragraph in Step 5 referencing signoff §2b `completion_manifest:` requirement.

### 2026-05-29 00:01 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_323546f0
completion_manifest:
  diff_reviewed: true
  scope_classification_complete: true
  no_hard_violations: true
Change verified: `default_artifact_checklist` is present in frontmatter with exactly the three required items (`diff_reviewed`, `scope_classification_complete`, `no_hard_violations`). Instruction paragraph in Step 5 correctly references signoff §2b. All acceptance criteria satisfied.

### 2026-05-29 00:02 — commit (status: ok)
feedback-id: fb_2026-05-29_ff4eb7b7
completion_manifest:
  staged_files_verified: true
  epic_scope_clean: true
  commit_successful: true
Committing batch of EPIC-CompletionManifestSignoff agent checklist tickets (02_02 through 02_06 plus other staged epic artifacts). All 20 staged files are within EPIC-CompletionManifestSignoff scope.
