---
title: "Document manifest validation step in building-epics skill"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 03_ticket_supervisor_manifest_validation.md
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

# 05: Document manifest validation step in building-epics skill

## Goal
In order to keep the building-epics skill (the supervisory runbook) in sync with the manifest validation logic added in ticket 03, we need to update `building-epics/SKILL.md` to describe the completion_manifest validation step as part of the ticket-level loop.

## Context
Depends on ticket 03 (ticket-supervisor §2.3). The building-epics skill is the single runbook loaded by both `epic-supervisor` and `ticket-supervisor`. It must document the manifest validation step so that any future reader of the skill understands where in the ticket loop it fires and what the expected outcomes are.

The update is additive: insert a §2.3 subsection under the existing §2 (five-step ticket loop) that cross-references the signoff skill §2b for the manifest format and describes the supervisory actions (proceed / downgrade-to-blocker / malformed-retry / legacy-skip).

## Acceptance Criteria
```gherkin
Given the building-epics skill is read
When the five-step ticket loop section is inspected
Then a §2.3 subsection describing completion_manifest validation is present

Given §2.3 in building-epics
When it is read
Then it references signoff skill §2b for the manifest format

Given §2.3 in building-epics
When the four supervisor actions are inspected
Then proceed, downgrade-to-blocker, malformed-retry, and legacy-skip are all described

Given the existing signoff parity guard description in building-epics
When it is read after this ticket
Then it is not removed or contradicted by the new §2.3 content
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert
- [ ] Insert §2.3 under the five-step ticket loop in `templates/skills/building-epics/SKILL.md` with the heading "§2.3 Completion Manifest Validation (post-comment-parse step)"
- [ ] Document the four supervisor actions in a table: all-true → proceed; ok+false → downgrade-to-blocker; malformed → retry-once; absent → warn+skip
- [ ] Add a cross-reference to signoff skill §2b for the manifest format definition
- [ ] Confirm the new section does not duplicate or contradict any existing §2.x content
- [ ] Add a note that the malformed-retry cap is 1 (one retry per manifest, not per item)

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Pure documentation edit to a skill template; fully reversible.
