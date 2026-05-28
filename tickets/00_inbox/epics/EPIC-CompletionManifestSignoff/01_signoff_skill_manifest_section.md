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
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
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

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert
- [ ] Insert §2b after §2a in `templates/skills/signoff/SKILL.md` documenting:
  - The `completion_manifest:` YAML block placement (after `feedback-id:` in the comment body)
  - Format rules: `true` items are bare; `false` items must be a nested object with `result`, `reason`, `remediation`
  - Bare `false` rule: supervisor treats as malformed and retries once
  - Legacy compatibility: manifests absent from pre-epoch tickets are accepted gracefully
- [ ] Add a `### §2b Manifest Examples` subsection with a copy-paste YAML example showing both a `true` item and a `false` nested-object item
- [ ] Update §3 Comment-Append Recipe to note that the manifest block is placed after `feedback-id:` and before the prose summary

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Pure doc edit to a template file; fully reversible.
