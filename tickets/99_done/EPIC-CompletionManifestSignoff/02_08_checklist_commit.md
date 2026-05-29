---
title: "Add default_artifact_checklist to commit"
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

- [x] documentation-expert — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:05
- [x] commit — 2026-05-29 13:10

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/commit.md` frontmatter: add `default_artifact_checklist: [pre_commit_hooks_pass, commit_message_valid, ticket_staged]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_611f8d36
completion_manifest:
  frontmatter_checklist_added: true
  instruction_paragraph_added: true
Added `default_artifact_checklist` YAML block to `templates/agents/commit.md` frontmatter with items pre_commit_hooks_pass, commit_message_valid, ticket_staged. Added a "Completion Manifest" section in the agent body referencing signoff §2b and the nested-object expansion rule for false items.

### 2026-05-29 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_2292c744
completion_manifest:
  acceptance_criteria_met: true
  frontmatter_checklist_correct: true
  instruction_paragraph_references_signoff_2b: true
All acceptance criteria met: `default_artifact_checklist` present in frontmatter with exactly the three required items (pre_commit_hooks_pass, commit_message_valid, ticket_staged). Instruction paragraph in body correctly references signoff §2b and explains the nested-object expansion rule for false values. No blockers.

### 2026-05-29 13:10 — commit (status: ok)
feedback-id: fb_2026-05-29_89991dbf
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Commit phase complete. `templates/agents/commit.md` with `default_artifact_checklist` landed in HEAD (captured in commit 66f373d during concurrent epic staging). Ticket sign-offs for documentation-expert and pr-reviewer are also committed. All three checklist items satisfied.
