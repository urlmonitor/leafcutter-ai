---
title: "Each epic ticket is written only inside the epic folder, with its back-reference pointing at the epic-folder path"
status: todo
source_ac: ACD-1200a-9
components:
  - ac-driven-dev
created: 2026-06-22
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/goal_to_epic.py
agents:
  python-coder: needed
  test-writer: needed
  test-runner: needed
  sql-coder: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Each epic ticket is written only inside the epic folder, with its back-reference pointing at the epic-folder path

## Actor / Goal

As the leafcutter-ai system, I want every generated epic ticket written to
exactly one location — inside the epic folder — with its `implemented_by`
back-reference naming that same epic-folder path, so that goal-mode `/build-ac`
runs leave no duplicate loose inbox tickets and no AC points at a path that
should not exist.

## Context

This ticket implements AC store entry `ACD-1200a-9` (component
`ac-driven-dev`, assigned `python-coder`, complexity M). It fixes defects #1
and #2 of the `goal_to_epic.py` known-quirks set: the generator currently
writes each ticket to `tickets/00_inbox/<file>.md` (loose) *and* copies it into
the epic folder, and stamps each source AC's `implemented_by` with the loose
inbox-root path instead of the epic-folder path.

Part of EPIC-GoalToEpicBugfixes. Sibling `02_basename_collision_resolution.md`
(ACD-1200a-9-i) builds on the single-location write contract established here.

## AC References

- Implements ACD-1200a-9 (single-location epic-folder ticket write + correct `implemented_by` back-reference)

## Acceptance Criteria

```gherkin
Given goal ACD-050 (title: "Validate API inputs") has 3 leaf ACs beneath it,
And the epic folder EPIC-ValidateApiInputs has been chosen as the assembly target,
When the system generates the ticket files for those leaf ACs,
Then each of the 3 ticket files exists only at one location, inside the epic
  folder under the tickets inbox (tickets/00_inbox/epics/EPIC-ValidateApiInputs/),
And no copy of any of those 3 ticket files exists at the tickets inbox root
  (tickets/00_inbox/) outside the epic folder,
And for each leaf AC, the implemented_by back-reference recorded in that AC's
  YAML names the ticket's path inside the epic folder
  (tickets/00_inbox/epics/EPIC-ValidateApiInputs/NN_*.md),
And no implemented_by back-reference names an inbox-root path
  (tickets/00_inbox/NN_*.md) for any of those tickets.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACD-1200a-9 | | | |

## Comments

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

- [ ] Locate the dual-write path in `goal_to_epic.py` (the loose `tickets/00_inbox/` write plus the epic-folder copy) and remove the loose write so only the epic-folder write remains.
- [ ] Ensure the `implemented_by` back-reference written onto each leaf AC names the epic-folder path the ticket was actually written to.
- [ ] Keep the ticket-file write and the `implemented_by` write consistent so an AC never ends a run pointing at a nonexistent path. Wrap file/YAML I/O per the project error-handling policy.
- [ ] Confirm idempotency: re-generating the same goal into the same epic folder does not multiply ticket files across locations.
- [ ] Tests for: single-location write, no inbox-root stray, epic-folder `implemented_by`, no inbox-root back-ref.

## Risk & Safety

- Touches money? No.
- Touches data? Yes — changes how `implemented_by` is stamped onto AC YAML; targeted field updates only.
- Reversibility? High — behavior-only change to a generator script.
