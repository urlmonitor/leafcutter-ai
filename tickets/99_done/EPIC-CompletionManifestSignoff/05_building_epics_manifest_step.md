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
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
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

- [x] documentation-expert — 2026-05-29 10:00
- [x] pr-reviewer — 2026-05-29 10:05
- [x] commit — 2026-05-29 10:10
- [ ] pull-request

## Comments

### 2026-05-29 10:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_6518e52f
completion_manifest:
  section_inserted: true
  four_actions_table_present: true
  signoff_skill_crossref_added: true
  no_duplication_or_contradiction: true
  malformed_retry_cap_noted: true
Inserted §2.3 "Completion Manifest Validation (post-comment-parse step)" into `templates/skills/building-epics/SKILL.md` between §2.2 (routing table) and the existing sign-off invariants section (renumbered §2.4). The new section includes a four-row supervisor routing table (all-true / ok-with-false / malformed / absent), a cross-reference to `signoff §2b` for the manifest format, a note that the malformed-retry cap is 1 per manifest invocation (not per item), and a legacy-compatibility paragraph. No duplication of or contradiction with existing §2.x content detected.

### 2026-05-29 10:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_99af5bcf
completion_manifest:
  section_placement_correct: true
  four_actions_all_present: true
  signoff_crossref_verified: true
  no_contradictions_found: true
  malformed_retry_cap_present: true
Reviewed the §2.3 insertion: all four supervisor actions (all-true/proceed, ok-with-false/downgrade-to-blocker, malformed/retry-once, absent/warn+skip) are correctly documented; cross-reference to `signoff §2b` confirmed present; former §2.3 correctly renumbered to §2.4 with no content change; no duplication or contradiction found. Approved.

### 2026-05-29 10:10 — commit (status: ok)
feedback-id: fb_2026-05-29_eaa0ae93
completion_manifest:
  files_staged_correctly: true
  commit_succeeded: true
  ticket_signoff_included: true
Committed `templates/skills/building-epics/SKILL.md` (§2.3 insertion, 24 lines added) and `tickets/00_inbox/epics/EPIC-CompletionManifestSignoff/05_building_epics_manifest_step.md` (sign-offs for documentation-expert, pr-reviewer, commit). Pull-request phase skipped per caller instruction (commit-to-worktree-only run).

## Implementation Tasks

### documentation-expert
- [x] Insert §2.3 under the five-step ticket loop in `templates/skills/building-epics/SKILL.md` with the heading "§2.3 Completion Manifest Validation (post-comment-parse step)"
- [x] Document the four supervisor actions in a table: all-true → proceed; ok+false → downgrade-to-blocker; malformed → retry-once; absent → warn+skip
- [x] Add a cross-reference to signoff skill §2b for the manifest format definition
- [x] Confirm the new section does not duplicate or contradict any existing §2.x content
- [x] Add a note that the malformed-retry cap is 1 (one retry per manifest, not per item)

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Pure documentation edit to a skill template; fully reversible.
