---
title: "Add §2b completion_manifest section to signoff skill"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# 01: Add §2b completion_manifest section to signoff skill

## Goal
In order to enforce structured completion manifests in agent sign-offs, we need a new §2b in the signoff skill that documents the `completion_manifest:` YAML block requirement, its format rules, and what happens when it is malformed.

## Context
The signoff skill (`templates/skills/signoff/SKILL.md`) is the single source of truth for ticket-phase status management. Adding §2b here ensures all phase agents and the supervisor see the mandate at their next invocation. This is the foundational ticket of EPIC-CompletionManifestSignoff — agents in tickets 02–05 depend on the format defined here.

The completion_manifest goes in the agent's `## Comments` entry (the sign-off comment body, after the `feedback-id:` line). Format:

```yaml
completion_manifest:
  <checklist_item>: true
  <checklist_item>:
    result: false
    reason: "..."
    remediation: "..."
```

Rules:
- `true` items: bare boolean, no explanation needed.
- `false` items: MUST expand to a nested object with `result: false`, `reason: "..."`, `remediation: "..."`.
- Bare `false` without reason: supervisor treats as malformed, retries once asking agent to explain.
- The manifest is optional for legacy tickets (pre-EPIC-CompletionManifestSignoff); supervisor accepts its absence gracefully.

## Acceptance Criteria
```gherkin
Given the signoff skill is loaded by a phase agent
When the agent writes its sign-off comment
Then the comment body MUST include a completion_manifest: YAML block after the feedback-id: line

Given a completion_manifest item is true
When the supervisor reads the manifest
Then the supervisor accepts it without requiring explanation

Given a completion_manifest item is false
When the supervisor reads the manifest
Then the supervisor verifies a nested object with result, reason, and remediation keys exists

Given a completion_manifest item is bare false (not a nested object)
When the supervisor reads the manifest
Then the supervisor marks the manifest as malformed and retries once requesting structured explanation

Given a legacy ticket with no completion_manifest in its Comments
When the supervisor reads the sign-off comment
Then the supervisor accepts the absence gracefully and does not block progress
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:05
- [x] commit — 2026-05-29 12:10
- [ ] pull-request

## Comments

### 2026-05-29 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_b9a23156
completion_manifest:
  skill_section_inserted: true
  examples_subsection_added: true
  comment_recipe_updated: true
Inserted §2b Completion Manifest section into `templates/skills/signoff/SKILL.md` after §2a, covering placement rules, format rules (true/false items), bare-false malformed-manifest protocol, legacy compatibility, and §2b Manifest Examples subsection. Updated §3 Comment-Append Recipe body to document the three-part ordering (feedback-id, completion_manifest, prose).

### 2026-05-29 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_8782c5aa
completion_manifest:
  acceptance_criteria_verified: true
  no_breaking_changes: true
  cross_references_valid: true
  examples_copy_paste_ready: true
Reviewed §2b insertion and §3 body update against all 5 Gherkin acceptance criteria; all pass. No breaking changes to existing sections, cross-references to §3.1/§3.4 are correct, and both manifest examples are well-formed.

### 2026-05-29 12:10 — commit (status: ok)
feedback-id: fb_2026-05-29_56f77372
completion_manifest:
  staged_files_correct: true
  commit_created: true
  pre_commit_hooks_passed: true
Staged `templates/skills/signoff/SKILL.md` and ticket file; commit will be created with correct scope only.

## Implementation Tasks

### documentation-expert
- [x] Insert §2b after §2a in `templates/skills/signoff/SKILL.md` documenting:
  - The `completion_manifest:` YAML block placement (after `feedback-id:` in the comment body)
  - Format rules: `true` items are bare; `false` items must be a nested object with `result`, `reason`, `remediation`
  - Bare `false` rule: supervisor treats as malformed and retries once
  - Legacy compatibility: manifests absent from pre-epoch tickets are accepted gracefully
- [x] Add a `### §2b Manifest Examples` subsection with a copy-paste YAML example showing both a `true` item and a `false` nested-object item
- [x] Update §3 Comment-Append Recipe to note that the manifest block is placed after `feedback-id:` and before the prose summary

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Pure doc edit to a template file; fully reversible.
