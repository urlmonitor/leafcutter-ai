---
title: "KI-BO-20260915-completed-sibling-in-a-halted-batch-is-reported-not-built — a ticket written `status: done` in the same batch as a refused sibling was never added to the run's own completed-work list"
description: "KI-BO-20260915-completed-sibling-in-a-halted-batch-is-reported-not-built — a ticket written `status: done` in the same batch as a refused sibling was never added to the run's own completed-work list"
type: reference
category: reference
status: active
created: '2026-09-15'
last_updated: '2026-09-21'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260915-completed-sibling-in-a-halted-batch-is-reported-not-built — a ticket written `status: done` in the same batch as a refused sibling was never added to the run's own completed-work list

> One known issue, authored inline on the EPIC-WorkIsOnlyEverMarkedFinishedThroughThe
> branch on 2026-09-15 and relocated into this file on 2026-09-21, when that branch merged
> `origin/main`'s split of the register. The content is unchanged from the branch's own
> version; only its location moved, so that main's new one-file-per-issue structure is not
> reverted by a long-lived branch that predates it. Index:
> [build-orchestration.md](../build-orchestration.md).

- **Severity:** medium — no record is written wrong; the run's own report of what it did is
  wrong.
- **Status:** resolved — see `BO-400e-2` (the fix)
- **Occurrences:** 1 (found by `BO-400e-2`'s own test-writer red-baseline pass, 2026-09-15;
  not previously observed in a real drive)
- **First seen:** 2026-09-15 · **Last seen:** 2026-09-15
- **Where:** `templates/workflows-js/build-feature.js`, the halted-batch return branch
  (`if (haltedTickets.length > 0 || withheldResults.length > 0)`) — `completedBatches` was
  otherwise only pushed at the bottom of the epic loop, which this branch returns before
  ever reaching.

**Symptom.** Drive an epic batch containing two tickets: one whose record names a phase as
needed with no sign-off (refused, per `BO-400a-2-i`/`BO-400e-1`'s guard) and one whose
record names the same phases with a sign-off for every one (the same-run control case
`BO-400e-2`'s own AC requires). The refused ticket's file correctly stays `status: todo`.
The control ticket's file is correctly written `status: done`. But the run's own top-level
payload never added the control ticket's path to `completedBatches` /
`completedWorkPaths()`, and the `message` field read "2 piece(s) of work in total were not
built: `<refused>`, `<control>`" — naming, by path, the ticket that WAS built.

**Why it matters.** This is `BO-400e-2`'s own "So" clause — "not a mechanism that has
simply stopped writing" — recurring one layer up, at the run's reporting layer instead of
the per-ticket write layer. The per-ticket decision was already correct: the guard from
`BO-400a-2-i`/`BO-400e-1` refuses one ticket and writes the other exactly as specified.
What was wrong is what the batch's own summary says happened. A caller reading only the
payload, not re-reading every ticket file on disk, would believe the control ticket had
failed too.

**Distinct from.** `KI-BO-20260831-1932` / `ADR-046` — the per-ticket write decision this
sits next to, already resolved by `BO-400e-1` and confirmed still correct here. Also
distinct from a ticket removed between two epic reads (`BO-300a-5-iii`): no removal is
involved, both tickets are processed together in the same batch, and one halts while the
other completes.

**Fix.** `build-feature.js`'s halted-batch return branch now computes
`succeededInBatch` — batch members that are neither in `haltedTickets` nor
`withheldResults` and whose own result carries `ticket_completed === true` — and pushes a
partial `completedBatches` entry for them *before* `completedForHalt` / `cmpForHalt` are
computed, so the existing `completedWorkPaths()` / `notYetAttemptedPaths` logic picks the
ticket up as completed with no further change needed downstream. No new function was
added, and the `BO-400a-2-i` refusal itself was not touched or re-implemented.

**Related.** `KI-BO-20260831-1932` (the per-ticket write decision this reporting bug sits
next to), `ADR-046` (the decision record for that fix), `BO-400e-2` (the AC/ticket whose
own test-writer red-baseline found this).

**Pattern:** the per-item decisions were all correct and the summary of them was not — a
report that contradicts the artefacts it is reporting on, which is only visible to someone
who re-reads the artefacts.
