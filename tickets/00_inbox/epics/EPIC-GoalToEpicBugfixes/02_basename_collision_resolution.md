---
title: "A ticket whose basename already exists at the epic-folder path is resolved deterministically, never duplicated to a second location"
status: todo
source_ac: ACD-1200a-9-i
components:
  - ac-driven-dev
created: 2026-06-22
depends_on:
  - 01_single_location_write_and_backref.md
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

# A ticket whose basename already exists at the epic-folder path is resolved deterministically, never duplicated to a second location

## Actor / Goal

As the leafcutter-ai system, I want a ticket whose computed basename already
exists at the epic-folder path resolved deterministically — by overwriting the
existing epic-folder file in place — so that re-runs converge on exactly one
ticket file per leaf AC and never mint a renamed sibling or a second copy
elsewhere.

## Context

This ticket implements AC store entry `ACD-1200a-9-i` (component
`ac-driven-dev`, assigned `python-coder`, complexity S). It is the edge-case
companion to `ACD-1200a-9`: given the single-location write contract, this
pins down what happens on a basename collision inside the epic folder.

Part of EPIC-GoalToEpicBugfixes. Depends on
`01_single_location_write_and_backref.md` (ACD-1200a-9), which establishes the
single-location write contract this edge case refines.

## AC References

- Implements ACD-1200a-9-i (deterministic in-place collision resolution)
- Depends on ACD-1200a-9 (single-location epic-folder write contract)

## Acceptance Criteria

```gherkin
Given the epic folder tickets/00_inbox/epics/EPIC-ValidateApiInputs/ already
  contains a file named 01_validate-input-schema.md from a prior run,
And the system is generating a ticket for a leaf AC whose computed filename is
  also 01_validate-input-schema.md,
When the system writes that ticket,
Then it resolves the collision deterministically by writing to the existing
  epic-folder path (overwriting it in place) and reports that the existing
  file was replaced,
And it does not create a second ticket file at any other location for that
  leaf AC (neither a renamed sibling inside the epic folder nor a copy at the
  tickets inbox root),
And after the run exactly one ticket file with that basename exists for that
  leaf AC, at the epic-folder path,
And the leaf AC's implemented_by back-reference names that single
  epic-folder path.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| ACD-1200a-9-i | | | |

## Comments

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

- [ ] On a basename collision inside the epic folder, overwrite the existing epic-folder path in place rather than minting a renamed sibling or a second copy elsewhere.
- [ ] Emit a report/log line at an appropriate severity stating the existing file was replaced, so the overwrite is observable and not silent.
- [ ] Ensure after the run exactly one ticket file with that basename exists (at the epic-folder path) and the AC's `implemented_by` names that single path, consistent with ACD-1200a-9. Wrap overwrite I/O per the project error-handling policy.
- [ ] Tests for: in-place overwrite on collision, no second-location copy, single resulting file, correct `implemented_by`.

## Risk & Safety

- Touches money? No.
- Touches data? Yes — overwrites a ticket file in place and updates `implemented_by`; targeted updates only.
- Reversibility? High — behavior-only change to a generator script.
