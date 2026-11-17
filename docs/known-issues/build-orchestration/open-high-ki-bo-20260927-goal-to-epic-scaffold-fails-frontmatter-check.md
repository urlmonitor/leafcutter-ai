---
title: "KI-BO-20260927-goal-to-epic-scaffold-fails-frontmatter-check — goal_to_epic.py writes an epic that its own repository's commit hook refuses"
description: "high — goal_to_epic.py names ticket files with an NN_ order prefix but writes depends_on entries as the bare filename, and writes Master_Plan.md without title and depends_on. check-doc-frontmatter then refuses the scaffold commit, so every /build-ac goal-mode epic needs hand repair before it can land."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-10-09'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20260831-1934.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-014.md
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

## Observed again, 2026-10-09

The epic from the symptom above could not be driven as generated. Beyond the frontmatter repair,
three structural defects surfaced while driving it, and the epic had to be re-cut by deliverable.

1. **Dependencies followed the AC tree, not the code.** Every child ticket depended on its
   composite parent's ticket. A parent cannot close before its children, because of
   `check-ticket-ac-status-parity` and `check-done-proof`. So the epic deadlocked after ticket 01,
   and commit `5395fad54` (2026-09-28) reversed the edges for 17 parents. That deadlock is
   `KI-ACD-20260831-1934`, shape 1.
2. **`files_touched` was empty or stale,** so the planner's only parallelism test (disjoint
   `files_touched`) had nothing to work with. Ticket 01, built in `b7c48169b`, needed its
   `files_touched` rewritten to the files that commit created (`5395fad54`).
3. **One ticket per AC was the wrong unit.** "Nearly every ticket edited the same maker files", and
   a producer the others needed (the shared test locator, BO-4300f-4) was ticket 58 of 59, so
   earlier tickets built stand-ins for it (ticket 02's Context).

The re-cut (`5ee13293e`, 2026-09-28) replaced 58 open tickets with 13 deliverable tickets (02-14).
Each covers several ACs, keeps composite ACs with their children, takes `depends_on` from the ACs'
Expects From contracts, and has accurate `files_touched`. A dry run of the full closing order then
passed `check-done-proof` and `check-ticket-ac-status-parity` with no violations.

**What has changed since.** On 2026-10-07, `49d6139f1` (BO-2600a-5) made `expects_from` edges order
the epic, through one shared prerequisite rule (`scripts/ac_store/epic_dependencies.py`,
`_scan_edges`, :86-116). It also drops a child's `depends_on` on its structural parent when the
parent's `expects_from` names that child. That addresses part of item 1, for parents that declare
`expects_from`. It does not change the granularity (still one ticket per leaf AC) or how
`files_touched` is filled. The generator was not re-run against BO-4300 to check.

**Fix direction, added.** Group ACs into tickets by shared code target (the files the ACs'
`it_requirements` name) rather than one per AC, keeping composites with their children. Fail
generation when a ticket's `files_touched` is empty while its ACs name implementation files.

**Related.** `KI-BO-014` (the `--ac` path's hygiene gaps).
