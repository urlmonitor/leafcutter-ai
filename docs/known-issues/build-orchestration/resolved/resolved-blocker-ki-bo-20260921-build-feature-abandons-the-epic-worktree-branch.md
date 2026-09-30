---
title: "KI-BO-20260921-build-feature-abandons-the-epic-worktree-branch — a re-run switches the worktree onto a fresh branch off main, drives the epic from the MAIN checkout, and re-runs tickets that are already committed"
description: "blocker — a second /build-feature run on an epic that already has committed work silently moves its worktree onto a new branch, reads the tickets from the main checkout where every phase still reads `needed`, and re-runs finished tickets while writing into main."
type: reference
category: reference
status: active
created: '2026-09-21'
last_updated: '2026-09-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260921-build-feature-abandons-the-epic-worktree-branch — a re-run switches the worktree onto a fresh branch off main, drives the epic from the MAIN checkout, and re-runs tickets that are already committed

> Index: [build-orchestration.md](../../build-orchestration.md).

- **Severity:** blocker. `/build-feature` cannot be re-run against an epic that already has committed work without corrupting that drive's state. The committed work is not destroyed, but it becomes invisible in the worktree, and the run does real damage in the one tree that should never be touched by a drive.
- **Status:** **RESOLVED 2026-09-23** — see the dated closure note at the foot of this entry.
  Original line, preserved: open — no AC. Observed once, end to end, with the full workflow journal retained.
- **Occurrences:** 1 (2026-09-21, `EPIC-FilesStayWorkable`, run `wf_39934043-41c`). Structural rather than incidental — nothing about the epic was unusual.
- **First seen:** 2026-09-21 · **Last seen:** 2026-09-21
- **Where:** `templates/workflows-js/build-feature.js`, the resolve/worktree-establish phase.

## Symptom, in the order it was noticed

The run reported `status: blocked`, halted at batch 1, with ticket 01 blocked on
`Phase 'architect-review' returned 'status: handoff' naming 'adr-author'`.

Ticket 01 was **already fully committed** on the epic branch at that moment — every
phase signed off, `work_status: done` in the AC store, commit `03913a68`.

Three separate things had gone wrong to produce that:

1. **The worktree had been switched onto a new branch.** It was on
   `EPIC-FilesStayWorkable`; after the run it was on `epic/files-stay-workable`,
   created off `origin/main`. `git log` in the worktree showed `d91e03ec`
   (origin/main) as HEAD, and the AC file read `work_status: todo` again — because
   that is main's copy, not the branch's.

   Nothing was lost: the original branch still held both commits. But a reader who
   trusted the worktree would conclude the work had vanished, and the obvious
   recovery — redo it — is exactly wrong.

2. **The epic was driven from the MAIN CHECKOUT.** The run's own result records
   `epic_path: /home/henzeh/projects/leafcutter/leafcutter-ai/tickets/00_inbox/epics/EPIC-FilesStayWorkable`
   while `worktree_path` correctly pointed at the worktree. Main's copies of the
   ticket files are the scaffold versions where every phase still reads `needed`,
   so the planner saw a completed ticket as untouched.

3. **Phase agents wrote into the main checkout.** After the run, `git status` in
   `leafcutter-ai` showed a **staged** 125-line edit to
   `01_TICKET-20260914-GE-127d-1.md`, a modified
   `docs/architecture/components/commit-guardian.md`, an untracked
   `docs/architecture/adrs/ADR-045-published-rule-reconciliation-gate.md`, and an
   untracked `.pending/` directory inside the epic folder.

   The re-run `architect-review` demanded an ADR that the ticket's own frontmatter
   says is not required (`requires_adr: false`) and that the first `architect-review`
   had already signed off without — an unsurprising outcome once the agent is handed
   a ticket whose recorded history has been rolled back to the scaffold.

## Why this is worse than a plain failure

A failed run wastes time. This one produced artifacts that look like progress — a new
ADR, a 125-line ticket update, sign-off comments — in a tree nobody was watching,
describing work that was already finished somewhere else. Merging any of it would have
duplicated ticket 01 against itself.

It also inverts the usual recovery instinct. The worktree is the place an operator
looks to see what a drive did; here the worktree was the misleading surface and the
abandoned branch held the truth.

## Related, and probably the trigger

`KI-BO-20260921-worktree-base-resolver-defaults-to-cwd` (filed alongside this one)
made the immediately preceding run abort with `worktree-base-unavailable` because the
base resolver ran from a cwd outside any git repository. Passing the worktree path
explicitly cleared that abort — and this behaviour is what the run did next. So the
branch-switching path may only be reachable once base resolution succeeds, which would
explain why it had not been seen before: earlier runs on this epic either died before
that point or created the worktree fresh.

That is a hypothesis about reachability, not a diagnosis of the branch-switch itself.
The branch-switch is a separate defect and needs its own reading of the establish step.

## Fix direction

- When the resolved worktree already exists, is a linked worktree of this repository,
  and is on a branch, **reuse that branch**. Creating a new branch off `origin/main`
  discards whatever the previous drive committed.
- Drive the epic from the resolved `worktree_path`, never from the main checkout. The
  run already computes both and uses the right one for `worktree-facts-resolved`; the
  epic-path derivation does not follow it.
- A phase agent writing to the main checkout during an epic drive should be treated as
  a hard error, not an outcome. Main is the one tree a drive must never touch.

## Recovery, for whoever hits this next

The committed work is on the original branch. `git -C <worktree> checkout <ORIGINAL-BRANCH>`
restores it. Then clean the main checkout: `git restore --staged --worktree` the tracked
files the drive touched and `git clean -fdn` to review the untracked ones before removing
them. Preserve any genuinely new artifact (here, the ADR) outside the tree first — it may
be worth keeping even though the run that produced it should not have happened.

**Pattern:** a resume path that re-derives state from the default branch instead of from
the work in progress, so a completed drive reads as an untouched one.

**Closed 2026-09-23.** Re-verified against the current code, not this entry's narrative. All
three fix-direction bullets above have landed, under the `BO-4000` family:

- **Branch reuse instead of a fresh branch off origin/main.** The resolve/worktree-establish
  block (`templates/workflows-js/build-feature.js`, ~lines 1416-1447) now runs two reuse
  checks before ever creating anything: Scenario 1 reuses `resolveResult.worktree_path`
  outright when `worktree_repo_facts.py facts` confirms it `exists`, `is_linked_worktree`,
  `!is_main_checkout`, and `same_repository`. Scenario 2, when that is absent, computes the
  fixed `instructedLocation` and reuses it when a linked worktree already sits there **on the
  target's own branch**; a location occupied by anything else is refused outright
  (`worktree-location-occupied`), not overwritten. Only when neither exists does it fall
  through to `branch-standing`, which itself REFUSES to proceed
  (`branch-has-unique-commits`) when the branch is both ahead and behind `origin/main` — the
  exact "discards whatever the previous drive committed" case this entry describes.
- **The epic is driven from the worktree, never the main checkout.** `epic_path` (the raw,
  possibly-main-checkout value from the resolve step) is now used only to compute
  `worktreeEpicPath = toWorktreePath(epic_path || target, realWorktreePath)` (line 2632).
  Every downstream read — `recheckEpicTicketSet()` and all four dispatch call sites (lines
  2968, 3324, 3393, 3456) — passes `worktreeEpicPath`, never the raw `epic_path`. `grep -n
  "epic_path\b" templates/workflows-js/build-feature.js` shows no other consumer of the raw
  value.
- **Verified by name and by test.** `BO-4000.yaml` ("reuses the worktree it resolved for the
  target... never inside a checkout"), `BO-4000a.yaml` (location-mismatch abort),
  `BO-4000b.yaml` (a behind-`origin/main` branch is never silently checked out), and
  `BO-4000c.yaml` (occupied-location / nested-worktree refusal) are all `work_status: done`.
  Five dedicated test files exist:
  `unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py`,
  `test_bo4000a_worktree_report_adjudication.py`,
  `test_bo4000b_branch_staleness_decision.py`,
  `test_bo4000c_start_location_and_occupancy.py`, and the shared `_bo4000_fixtures.py`.
- **The third fix-direction bullet (a phase agent writing to the main checkout should be a
  hard error)** is not implemented as an independent guard — but is structurally moot given
  the two fixes above: the epic is never read from or dispatched against the main checkout
  path in the first place, so there is no longer a code path that could reach it.
- **Not verified end-to-end.** No live two-run `/build-feature` repro (first run commits,
  second run re-invoked) was executed as part of this closure; the verdict rests on the
  resolve/establish code path and the AC store's own recorded test coverage, not a fresh
  `wf_*` run against a real epic.
