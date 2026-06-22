---
title: "EPIC: goal_to_epic.py bug fixes — single-location writes, correct back-refs, apostrophe-safe epic names"
type: epic
status: in_progress
components:
  - ac-driven-dev
created: 2026-06-22
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: goal_to_epic.py Bug Fixes

## Goal

`scripts/goal_to_epic.py` (the engine behind `/build-ac` goal mode) has three
defects that force manual cleanup after every run. This epic fixes all three so
that pointing `/build-ac` at a goal produces a correct work package with no
post-run bookkeeping.

## Problem

Three defects, observed repeatedly during real goal-mode runs:

1. **Duplicate loose inbox tickets.** Each generated ticket is written into
   `tickets/00_inbox/<file>.md` (loose) *and* copied into the epic folder
   `tickets/00_inbox/epics/EPIC-<Name>/`, leaving the loose originals behind.
   `ticket-prioritizer` then builds every ticket twice.

2. **`implemented_by` stamped at the wrong path.** The back-reference written
   onto each source AC names the *inbox-root* loose path, not the
   epic-folder path — so the AC points at a location that should not exist.

3. **Apostrophes break derived epic names.** Epic-folder name derivation
   PascalCases the goal title but mishandles apostrophes / quote characters
   (e.g. `EPIC-Eachstage'sacoutputiscommittedtogit`), producing names that
   break shell globs and tooling. (Length-based truncation was already fixed
   separately by ACD-1200a-6.)

## Solution

Each defect maps to an already-approved acceptance criterion in the AC store
under `docs/acceptance-criteria/ac-driven-dev/ACD-1200-goal-to-epic/`:

- **ACD-1200a-9** — single-location epic-folder write + epic-folder
  `implemented_by` back-reference (fixes defects #1 and #2).
- **ACD-1200a-9-i** — deterministic in-place resolution when a ticket basename
  already exists at the epic-folder path (no second copy, no renamed sibling).
- **ACD-1200a-3-ii** — strip apostrophes / single+double quotes / backticks
  (ASCII U+0027/U+0022/U+0060 and curly U+2019) in-place before PascalCasing
  the epic folder name (fixes defect #3).

## Sub-Ticket Table

| # | File | Description | Agent | ACs | Depends On | Status |
|---|------|-------------|-------|-----|------------|--------|
| 01 | [01_single_location_write_and_backref.md](./01_single_location_write_and_backref.md) | Write each ticket only inside the epic folder; stamp `implemented_by` at the epic-folder path, never the inbox root | python-coder | ACD-1200a-9 | — | `[ ]` |
| 02 | [02_basename_collision_resolution.md](./02_basename_collision_resolution.md) | Resolve an existing epic-folder basename deterministically (overwrite in place); never duplicate to a second location | python-coder | ACD-1200a-9-i | 01 | `[ ]` |
| 03 | [03_apostrophe_safe_epic_names.md](./03_apostrophe_safe_epic_names.md) | Strip apostrophes/quote characters in-place before PascalCasing the epic folder name | python-coder | ACD-1200a-3-ii | — | `[ ]` |

## Dependency Graph

```
01_single_location_write_and_backref   (single-location write + correct back-ref)
        |
        v
02_basename_collision_resolution        (collision handling builds on the single-location contract)

03_apostrophe_safe_epic_names           (independent — epic-name derivation)
```

Parallel batches:
- **Batch 1**: 01 and 03 (independent; both edit `goal_to_epic.py`, so the
  supervisor serializes them under the files-touched gate even though there is
  no logical dependency).
- **Batch 2**: 02 (depends on 01).

## Files to Touch

```
scripts/goal_to_epic.py   # all three fixes land here
```

## Exit Criteria

- ACD-1200a-9, ACD-1200a-9-i, and ACD-1200a-3-ii all have `work_status: done`.
- A goal-mode `/build-ac` run leaves zero loose `tickets/00_inbox/TICKET-*.md`
  strays and every touched AC's `implemented_by` names an epic-folder path.
- A goal whose title contains an apostrophe yields a clean PascalCase epic name
  with no literal quote and no broken segment.
- `build-self.sh` passes with no errors.

## Risk & Safety

- Touches money? No.
- Touches data? Yes — the fix changes how `goal_to_epic.py` writes ticket files
  and stamps `implemented_by` on AC YAML. All AC mutations remain targeted field
  updates per the existing convention.
- Reversibility? High — behavior-only changes to a generator script; no schema
  or data migration.
