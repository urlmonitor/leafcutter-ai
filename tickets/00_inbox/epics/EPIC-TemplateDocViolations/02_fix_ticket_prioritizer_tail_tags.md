---
title: "Fix missing tail-tags in ticket-prioritizer skill DECISION HISTORY entries"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: high
phase: "Phase 1"
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - leafcutter-ai/templates/skills/ticket-prioritizer/scripts/prioritize.py
agents:
  architect-review: not_needed
  python-coder: needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  status-checker: not_needed
  sql-coder: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# 02: Fix missing tail-tags in ticket-prioritizer skill DECISION HISTORY entries

## Goal

In order to make the ticket-prioritizer skill script pass the `check_documentation`
pre-commit hook when installed into any downstream project, we need to append valid
tail-tags to both DECISION HISTORY entries in `prioritize.py` that currently lack
them.

## Context

The `check_documentation.py` hook enforces that every DECISION HISTORY entry ends
with either `(#EPIC-Name/NN)` or `(#TICKETLESS reason=<>=10-char reason>)`.

`leafcutter-ai/templates/skills/ticket-prioritizer/scripts/prioritize.py` has a
DECISION HISTORY block at the bottom of the file (lines 539-549) with two entries,
both missing tail-tags:

```
- 2026-05-13 13:00 [Agent]: Created as part of ticket 17 (EPIC-PortableDevWorkflow).
  Rewrote the previous priority-only script to resolve depends_on chains via
  a DAG with cycle detection. Kept dependency-free (stdlib only) so it can
  be copied into any project without Poetry/pip requirements.
- 2026-05-13 17:00 [Agent]: Ticket 19 — added 99_done to DONE_DIR_NAMES to match
  the renamed done folder (09_done → 99_done per ticket lifecycle manifest update).
```

Note: this DECISION HISTORY block is in a **module-level string literal** (plain
`"""..."""` at the bottom of the file, not a function docstring). The hook still
catches it. The entries must be fixed in-place without restructuring the block.

The appropriate tail-tags are:
- Entry 1: `(#TICKETLESS reason=initial-dag-implementation)` — 30 chars, valid
- Entry 2: `(#TICKETLESS reason=99-done-dir-name-alignment)` — 34 chars, valid

## Acceptance Criteria

```gherkin
Given a downstream project built from the updated leafcutter templates
When the pre-commit hook check_documentation runs on prioritize.py
Then no "Missing tail-tag" violations are reported for that file

Given the updated prioritize.py DECISION HISTORY block
When inspected
Then the 2026-05-13 13:00 entry ends with (#TICKETLESS reason=initial-dag-implementation)
And the 2026-05-13 17:00 entry ends with (#TICKETLESS reason=99-done-dir-name-alignment)
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit

## Comments

## Implementation Tasks

- [ ] In `leafcutter-ai/templates/skills/ticket-prioritizer/scripts/prioritize.py`,
  append ` (#TICKETLESS reason=initial-dag-implementation)` to the end of the
  `2026-05-13 13:00 [Agent]: Created as part of ticket 17 ...` first-line of that entry
- [ ] In the same file, append ` (#TICKETLESS reason=99-done-dir-name-alignment)` to
  the end of the `2026-05-13 17:00 [Agent]: Ticket 19 — added 99_done ...` first-line
- [ ] Add a DECISION HISTORY entry to the file documenting this fix
  (with HH:MM and `(#EPIC-TemplateDocViolations/02)` tail-tag)

## Risk & Safety

- Touches money? No.
- Touches data? No. Template source file only; no runtime data affected.
- Reversibility? Fully reversible; the change is a string append to comment lines.
