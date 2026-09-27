---
title: "KI-BO-20260927-goal-to-epic-scaffold-fails-frontmatter-check — goal_to_epic.py writes an epic that its own repository's commit hook refuses"
description: "high — goal_to_epic.py names ticket files with an NN_ order prefix but writes depends_on entries as the bare filename, and writes Master_Plan.md without title and depends_on. check-doc-frontmatter then refuses the scaffold commit, so every /build-ac goal-mode epic needs hand repair before it can land."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
---

# KI-BO-20260927-goal-to-epic-scaffold-fails-frontmatter-check — goal_to_epic.py writes an epic its own commit hook refuses

- **Severity:** high. It fails closed: the scaffold cannot be committed. Every goal-mode
  `/build-ac` run needs a hand repair, and a hand repair is where drift between tickets and
  the dependency graph gets in.
- **Status:** open, no AC. Observed 2026-09-27 on `goal_to_epic.py --ac BO-4300 --approved-only`,
  which generated EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace with 59 tickets.
- **Where:** `.leafcutter/scripts/ac_store/goal_to_epic.py` (source under `templates/scripts/ac_store/`),
  and the ticket generator it calls for each leaf.

## Symptom

The scaffold commit was refused by `check-doc-frontmatter` on 22 files:

- 21 tickets, each with a dependency. A `depends_on` entry such as
  `TICKET-20260927-BO-4300a-1.md` was not found, because the file on disk is
  `01_TICKET-20260927-BO-4300a-1.md`.
- `Master_Plan.md`: missing required fields `title` and `depends_on`.

## Mechanism

The epic assembler adds an `NN_` topological-order prefix to each ticket's filename after the
ticket (and its `depends_on` list) has been written under the bare name. The references are
never rewritten to the prefixed names. Every epic already on main uses the prefixed names in
`depends_on`, and all 40 tracked Master_Plans carry frontmatter with `title`. The generator
matches neither convention.

A related oddity, not a hook failure: each AC's `implemented_by` points at
`tickets/00_inbox/TICKET-<date>-<id>.md`, but the ticket lives inside the epic folder under its
prefixed name.

## Workaround used

A one-off script rewrote each `depends_on` entry to the prefixed filename that exists in the
folder, and added `title` and `depends_on: []` to Master_Plan. After that, every reference
resolved.

## Fix direction

- Assign the order prefixes before writing the tickets, or rewrite `depends_on` after renaming.
  Then assert that every `depends_on` entry names a file that exists in the epic folder.
- Emit `title` and `depends_on` in Master_Plan's frontmatter.
- Point `implemented_by` at the ticket's final path.
- Add a behavioural test that runs the generator on a fixture tree with dependencies, then runs
  the frontmatter checker over the output. It must exit 0.
