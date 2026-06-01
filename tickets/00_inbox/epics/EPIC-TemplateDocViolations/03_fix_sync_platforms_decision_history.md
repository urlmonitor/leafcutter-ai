---
title: "Fix missing HH:MM time in sync_platforms.py DECISION HISTORY entry"
status: todo
components:
  - sync_platforms
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
  - leafcutter-ai/templates/scripts/sync_platforms/sync_platforms.py
  - scripts/sync_platforms/sync_platforms.py
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

# 03: Fix missing HH:MM time in sync_platforms.py DECISION HISTORY entry

## Goal

In order to make `sync_platforms.py` pass the `check_documentation` pre-commit
hook in downstream projects, we need to add the mandatory `HH:MM` time component
to the DECISION HISTORY entry in both the template source and the deployed copy
in this repo, so that the entry matches the format `- YYYY-MM-DD HH:MM [Author]:`.

## Context

The `check_documentation.py` hook requires every DECISION HISTORY entry to start
with `- YYYY-MM-DD HH:MM` — the HH:MM component is mandatory.

Both copies have the same violation:

**Template** (`leafcutter-ai/templates/scripts/sync_platforms/sync_platforms.py`, line 206):
```
# - 2026-05-22 [python-coder/Ticket-10]: Initial implementation of bidirectional
```

**Deployed copy** (`scripts/sync_platforms/sync_platforms.py`, line 206):
```
# - 2026-05-22 [python-coder/Ticket-10]: Initial implementation of bidirectional
```

The fix is to insert a time `10:00` (a reasonable placeholder for a morning
implementation session) between the date and the author bracket. The exact
commit time is not known; `10:00` is documented as approximate.

Additionally, the entry is missing a tail-tag. The fix should also add
`(#TICKETLESS reason=initial-sync-implementation)` to comply with the tail-tag rule.

## Acceptance Criteria

```gherkin
Given a downstream project built from the updated sync_platforms.py template
When the pre-commit hook check_documentation runs on scripts/sync_platforms/sync_platforms.py
Then no "DECISION HISTORY entry incorrectly formatted" violation is reported

Given the updated template file leafcutter-ai/templates/scripts/sync_platforms/sync_platforms.py
When inspected
Then line 206 reads: # - 2026-05-22 10:00 [python-coder/Ticket-10]: Initial implementation of bidirectional  (#TICKETLESS reason=initial-sync-implementation)

Given the deployed copy scripts/sync_platforms/sync_platforms.py
When inspected
Then line 206 has the same corrected format
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit

## Comments

## Implementation Tasks

- [ ] In `leafcutter-ai/templates/scripts/sync_platforms/sync_platforms.py`, change:
  `# - 2026-05-22 [python-coder/Ticket-10]: Initial implementation of bidirectional`
  to:
  `# - 2026-05-22 10:00 [python-coder/Ticket-10]: Initial implementation of bidirectional  (#TICKETLESS reason=initial-sync-implementation)`
- [ ] Apply the identical fix to `scripts/sync_platforms/sync_platforms.py` (the
  deployed copy currently in this repo)
- [ ] Add a new DECISION HISTORY entry to both files documenting this fix
  (with today's date, HH:MM, and `(#EPIC-TemplateDocViolations/03)` tail-tag)

## Risk & Safety

- Touches money? No.
- Touches data? No. Comment-only change in Python source files.
- Reversibility? Fully reversible; comment-only edit.
