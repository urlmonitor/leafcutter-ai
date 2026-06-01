---
title: "Add artifact_checklist to ticket-authoring frontmatter schema"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_signoff_skill_manifest_section.md
priority: medium
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
  commit: failed
  pull-request: needed
---

# 04: Add artifact_checklist to ticket-authoring frontmatter schema

## Goal
In order to let tickets customise or extend the agent's default artifact checklist, we need to add `artifact_checklist:` as an optional frontmatter field in the ticket-authoring skill's schema reference and examples.

## Context
Depends on ticket 01 (manifest format) and is referenced by ticket 03 (supervisor validation). The `artifact_checklist:` field at the ticket level merges with each phase agent's `default_artifact_checklist` when the supervisor builds the expected checklist for that invocation. Items in the ticket list extend the agent defaults; if a ticket item has the same key as an agent default, the ticket value takes precedence (override semantics).

This ticket is documentation-only: it adds the field to the skill's frontmatter schema table and the "Required vs Optional" table, and updates the frontmatter example block. No code change is needed — the supervisor's merge logic (ticket 03) reads the field at runtime.

The field format in ticket frontmatter:
```yaml
artifact_checklist:
  python-coder:
    - linting_clean
    - type_annotations_added
  pr-reviewer:
    - changelog_reviewed
```

Keys are agent names; values are lists of item names that extend that agent's default checklist for this specific ticket.

## Acceptance Criteria
```gherkin
Given the ticket-authoring skill is read
When the frontmatter schema table is inspected
Then an artifact_checklist row is present, marked optional, with a description of merge semantics

Given a ticket is authored with artifact_checklist for python-coder
When the ticket is written and the frontmatter guard runs
Then no guard error fires (the field is valid frontmatter)

Given the ticket-authoring skill example block
When it is read
Then a commented-out artifact_checklist example is visible showing the per-agent nested structure
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:01
- [ ] commit — failed 2026-05-29 12:02
- [ ] pull-request

## Comments

### 2026-05-29 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_f50d8a40
completion_manifest:
  artifact_checklist_row_added: true
  frontmatter_example_updated: true
  common_mistakes_row_added: true
Added artifact_checklist field to templates/skills/ticket-authoring/SKILL.md: inserted optional row in the Required vs Optional table, added a commented-out three-line example block in the frontmatter schema, and appended a Common Mistakes row for the agent-name vs item-name keying mistake.

### 2026-05-29 12:01 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_847ef706
completion_manifest:
  changes_match_acceptance_criteria: true
  artifact_checklist_row_correct: true
  frontmatter_example_well_formed: true
  common_mistakes_row_accurate: true
All three documentation changes are correct and complete. The artifact_checklist row in the Required vs Optional table carries the right description. The commented-out frontmatter example shows the correct per-agent nested structure. The Common Mistakes row correctly identifies the keying mistake. No issues found; approved for commit.

### 2026-05-29 12:02 — commit (status: blocker)
feedback-id: (submit-failed)
completion_manifest:
  files_staged:
    result: false
    reason: "C: drive at 100% capacity (7.9MB free); git index write fails with 'unable to write new index file'."
    remediation: "Free disk space on C: (at least ~100MB), then re-run the commit phase: git add templates/skills/ticket-authoring/SKILL.md tickets/00_inbox/epics/EPIC-CompletionManifestSignoff/04_ticket_authoring_artifact_checklist.md && git commit."
Attempted to stage files but git add failed because the C: drive is full (237G used, 7.9M free). All documentation edits are on disk and correct; only the git staging/commit step is blocked. Free disk space and retry.

## Implementation Tasks

### documentation-expert
- [x] Add `artifact_checklist` row to the "Required vs Optional" table in `templates/skills/ticket-authoring/SKILL.md` (optional, with description: "Per-agent checklist overrides. Map of agent-name → list of item names. Merges with agent's default_artifact_checklist; ticket items extend defaults, same key overrides.")
- [x] Add `artifact_checklist:` to the frontmatter schema example block as a commented-out optional field with a one-line example showing one agent key
- [x] Update the "Common Mistakes" table with a row: "artifact_checklist keyed by item name instead of agent name | Must be a map of agent-name → list"

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Pure documentation edit; no hook or enforcement change. The field is optional and its absence is valid.
