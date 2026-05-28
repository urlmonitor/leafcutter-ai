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
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
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

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert
- [ ] Add `artifact_checklist` row to the "Required vs Optional" table in `templates/skills/ticket-authoring/SKILL.md` (optional, with description: "Per-agent checklist overrides. Map of agent-name → list of item names. Merges with agent's default_artifact_checklist; ticket items extend defaults, same key overrides.")
- [ ] Add `artifact_checklist:` to the frontmatter schema example block as a commented-out optional field with a one-line example showing one agent key
- [ ] Update the "Common Mistakes" table with a row: "artifact_checklist keyed by item name instead of agent name | Must be a map of agent-name → list"

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Pure documentation edit; no hook or enforcement change. The field is optional and its absence is valid.
