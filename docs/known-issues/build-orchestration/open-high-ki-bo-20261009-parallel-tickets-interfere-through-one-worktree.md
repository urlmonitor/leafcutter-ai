---
title: "KI-BO-20261009-parallel-tickets-interfere-through-one-worktree — /build-feature runs a batch's tickets concurrently in one epic worktree, and its only coupling test is disjoint files_touched, so one ticket's half-written file broke another ticket's tests and build"
description: "high — tickets 02 and 05 of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace ran in the same batch because their files_touched were disjoint. Ticket 02's tests build the deployed layout from the shared templates/ tree, and ticket 05's in-flight templates/scripts/worktree_readiness.py held a NUL byte, so build.py's closure guard refused and 02's test-runner and ac-fulfillment-gate failed on 05's unfinished work. 05's staged files then stopped 02's commit. The files_touched test cannot see test-fixture or deployed-install coupling."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260901-0920.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260927-file-size-hook-read-another-worktrees-index.md
---

# KI-BO-20261009-parallel-tickets-interfere-through-one-worktree — disjoint files_touched is not independence

- **Severity:** high. A ticket's gates report failures caused by a sibling's unfinished work. The
  failures look like the ticket's own defects (test-runner blamed a "flaky" build), so a phase
  agent can be sent to fix code that is not broken. The remedies that worked were all manual:
  re-ordering dependencies so the two tickets never share a batch.
- **Status:** open, no AC. Observed and diagnosed in the ticket's own Comments.
- **Occurrences:** 3 incidents. Tickets 02 and 05, 2026-09-30: the coordinator then serialised 02
  after 05 (`731e7a930`) and 06 after 02 (`b30e18b94`) to stop it recurring. Tickets 07 and 08,
  2026-10-12: committed from separate lane worktrees (see "Observed again" below). GE-124 epic,
  2026-10-25: per-ticket commits refused by check-build-drift on siblings' templates (see the
  2026-10-25 note).
- **First seen:** 2026-09-30 · **Last seen:** 2026-10-25
- **Where:** `templates/workflows-js/build-feature.js`: the planner's only physical-coupling rule is
  "no two tickets share any files_touched entry" (:3079). A batch's tickets are dispatched together
  through `parallel()` in chunks of `BATCH_SIZE` (:3305-3445), all in `realWorktreePath`.

## Symptom

Ticket 02's comments on 2026-09-30, in order:

- **test-runner (blocker):** 10 failed, 47 passed, with counts varying run to run (35 failed on an
  earlier run). "Also flaky: `scripts/build.py` exits 1 on an empty target dir", which made
  `ensure_deployed_layout` raise `DeployedMakerNotFoundError` in some runs.
- **ac-fulfillment-gate (blocker):** both `_MANUAL` tests of BO-4300f-4 errored because
  `scripts/build.py --target-dir <tmp>` exited 1. The gate attributed that to
  `scripts/ac_store/_ac_components.py` line 60.
- **commit (blocker):** "the shared index holds staged work from tickets 04/05
  (`worktree_readiness.py`, `precommit_canary.py`, `test_bo_4300c_1*`, ticket 05) that does not
  belong in this commit". Nothing was committed.
- **python-coder (handoff), the diagnosis:** the build failure was "a literal NUL byte in the
  unstaged working copy of `templates/scripts/worktree_readiness.py` (ticket 05's in-flight file),
  tripping the closure guard 'UNANALYSABLE SCRIPT ... null bytes'". Once it was removed,
  `build.py --target-dir` exited 0. No fixture change was needed.

## Mechanism

1. **The planner tests only declared file overlap.** 02 owns `unit_tests/build_orchestration/*`
   fixtures, and 05 owns `templates/scripts/worktree_readiness.py` and friends. Their
   `files_touched` are disjoint, so rule (3) put them side by side.
2. **02's tests read 05's files anyway.** BO-4300f-4's proof runs the deployed maker. Its fixture
   builds a deployed layout from the worktree's whole `templates/` tree, which includes every
   sibling's half-written template. Neither `files_touched` list can express that, because the
   dependency runs through the build, not through a file either ticket edits.
3. **The index is shared as well.** Staged files from 05's phases were in the index when 02's commit
   ran. `KI-BO-20260901-0920` covers that half (see its 2026-10-09 note).
4. **The gates do not know the worktree is shared.** Each gate reports on the whole worktree as if
   it were the ticket's own. Nothing tells the agent that the failing file belongs to a sibling in
   flight.

## Impact

Three gates on 02 failed for 05's reasons, a python-coder dispatch was spent on a diagnosis, the
ticket was reopened (`731e7a930`), and two dependency edges had to be added by hand to serialise
work that the plan had declared independent. The same shape applies to any pair where one ticket's
tests build, install or import what the other is editing.

## Detection

A gate failure that names a file outside the failing ticket's `files_touched`, during a batch with
more than one ticket. Or a failure that disappears when the batch is re-run one ticket at a time.

## Fix direction

- Give each ticket in a parallel batch its own worktree (or its own sparse checkout), branched from
  the epic branch, and merge back at commit. That makes `files_touched` disjointness a real
  guarantee instead of a hint.
- Failing that, treat any ticket that builds the deployed layout, installs, or edits `templates/`
  as coupled to every other ticket that does, and never batch two of them.
- Have gate agents name any failing path outside the ticket's `files_touched` as "sibling-owned"
  rather than as the ticket's defect.

**Related.** `KI-BO-20260901-0920` (no lock on the shared index; it predicted the staged-files
half). `KI-CG-20260927-file-size-hook-read-another-worktrees-index` is the cross-worktree form of
"a gate saw someone else's changes".

## Observed again, 2026-10-13: path-limited commits do not isolate the gates

**Where:** tickets 07 and 08 of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, 2026-10-12. The
refusals are from the coordinator's session account. Hook scope is verified on `origin/main`
`964f23a60`, and the lanes are verified on the epic branch.

**What happened.**

- A path-limited commit of one ticket (`git commit --only <its paths>`) still failed
  `check-build-drift` and `check-output-drift`, because another ticket had template edits in flight in
  the same worktree.
- A commit agent unstaged another ticket's newly added files to keep them out of its own commit. That
  turned them into untracked files.
- To get the two tickets in, the coordinator committed each from its own lane worktree and
  fast-forwarded the epic branch onto them. Ticket 07 records "Committed ... in lane worktree
  bo4300-lane07 (branch lane/bo4300-t07)" (`07_TICKET-...-safe-re-request.md:894`). Ticket 08 records
  "clean lane worktree lane/bo4300-t08" (`08_TICKET-...-locate-and-clear.md:967`). Their commits
  `c9f1a8a95` and `c0fa00e94` sit on the epic's first-parent line.

**Why a pathspec does not help.** Both hooks are registered `pass_filenames: false` and
`always_run: true`, and both read the worktree, not the commit:

- `check-build-drift` compares every template in its scope (`templates/agents/`,
  `templates/scripts/commit_guardian/`) with the install's build manifest
  (`check_build_drift.py:37-42`).
- `check-output-drift` hashes the output files it finds on disk (`check_output_drift.py:25-35`, `:216`).

So `--only` narrows what is committed, not what is checked. A sibling's half-edited template fails
every ticket's commit.

**Why unstaging is unsafe.** A newly added file that is unstaged is held by nothing: not the index, not
history. In a worktree that agents share, an untracked file can disappear in the next clean-up or
restore.

**What this adds.** It confirms the first fix direction above, one worktree per ticket: the lanes worked.
It also rules out the two cheaper substitutes. Those were tried, and both failed. The lanes cost a
manual set-up and a fast-forward per ticket, which the drive should do itself.

## Observed again, 2026-10-25: pre-commit's stash makes a sibling's template look drifted

**Where:** the GE-124 epic drive (`epic/every-screen-says-which-requirement-it-is`), per-ticket
commits from the shared epic worktree.

**What happened.** Each per-ticket commit failed `check-build-drift` on templates that belonged to
other tickets, for example `check_ac_schema.py`. pre-commit stashes unstaged changes before running
hooks. A sibling's modified template therefore reverted to its HEAD content while the hooks ran,
but its deployed copy had already been rebuilt from the new content. The hook compared the two and
reported drift. So the mechanism is slightly different from the 2026-10-13 occurrence: there a
half-edited template was on disk; here the template was finished and the stash put the old
version back for the duration of the hook.

**Workaround used.** One combined commit for all the tickets in the tree, `10ceb6c9d` on the epic
branch.

**What this adds to the fix direction.**

- Have `check-build-drift` compare against the staged index (or `git show :<path>`), not against
  the tree pre-commit restores from its stash. The tree it reads during a hook is neither the
  commit nor the working copy.
- Or have the drive commit each ticket right after its phases finish, before a sibling's work is
  in the tree. One worktree per ticket (above) also removes it.
