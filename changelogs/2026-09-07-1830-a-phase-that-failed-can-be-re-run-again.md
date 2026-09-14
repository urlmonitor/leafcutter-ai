---
title: "A phase that failed can be re-run again"
date: "2026-09-07"
time: "18:30"
type: manual
components:
  - build_orchestration
  - supervisor_system
summary: "Fixes KI-BO-20260907-1555 in both drivers: the dispatch set is now selected by a pure, executable selectDispatchableByStatus() that keeps needed AND failed, so a phase that exhausted the failure-adjudication ladder is no longer discarded by every later drive. Measured on GE-120 ticket 36's real frontmatter, the old predicate dispatched 0 phases and the new one dispatches 5."
description: "build-ticket.js and build-feature.js each computed their dispatch set with a single inline filter on status === 'needed', while the planner's own schema enum reports four states including 'failed'. A phase that exhausted the within-drive retry ladder was therefore enumerated by the planner and then silently discarded, and nothing anywhere transitioned it back to needed, which made failed a write-only terminal state whose only exit was a human editing frontmatter by hand. GE-120 ticket 36 reached that state with four failed phases and zero needed ones; re-driving it dispatched no phase agent at all and wrote no code, and the implementation was produced only by abandoning the workflow and calling python-coder directly. The inline filter in both files is replaced by a pure, named selectDispatchableByStatus(orderedPhases) that selects needed or failed. It is a function rather than a widened inline filter for two reasons: the failed half is a decision that has to be readable at the call site, and a pure top-level function can be extracted and executed under node by the unit layer, which is what the new test does — running the real on-disk function from both files against ticket 36's actual frontmatter rather than a hand-typed copy, per the pattern test_bo_2700_defer_epic_pr.py established. The load-bearing question was whether re-dispatch terminates, and it does: on success a phase agent SETS signed_off rather than find-replacing the literal needed, so the failed row is cleared and the phase does not return on the next drive; on failure it stays failed, where it already was. The within-drive retry ladder is untouched. This also makes the driver match the state machine the signoff skill already documented — failed to signed_off after rework — which the dispatcher had simply never implemented. Two negative controls guard the boundary the fix must not cross: signed_off and not_needed are asserted NOT dispatchable, since widening to either would re-run passed work on every drive. A twin test asserts the two drivers carry byte-identical copies of the predicate, because the original defect was present in both and a fix to one is not a fix to the other. Deliberately not done: a cross-drive attempt counter, which was part of the original fix direction. Without it a genuinely unfixable phase is retried once per re-drive — operator-gated rather than automatic, and strictly better than the dead end it replaces, but it means an unattended epic re-drive now spends one attempt per failed phase. The KI entry is kept in the register rather than deleted, marked resolved, because its reasoning is why the predicate is shaped the way it is and the code cites it by id."
breaking: false
---

## Entry

### The defect

Both drivers selected phases to dispatch with one filter:

```js
orderedPhases.filter((p) => p.status === "needed")
```

The planner reports **four** states — `needed`, `signed_off`, `not_needed`, `failed`. So a
phase that exhausted the retry ladder was enumerated and then **discarded**, and nothing
transitioned it back. `failed` was write-only; re-running the drive was a no-op.

### Measured, on GE-120 ticket 36's real frontmatter

| predicate | phases dispatched |
|---|---|
| old (`needed` only) | **0** |
| new (`needed` or `failed`) | **5** |

### Why re-dispatch terminates

On success a phase agent **sets** `signed_off` rather than find-replacing the literal
`needed`, so the `failed` row is cleared. On failure it stays `failed`, where it already was.
The within-drive ladder is untouched. The driver now matches the state machine the signoff
skill already documented (*"`failed` → `signed_off` after rework"*) and had never implemented.

### Coverage

21 tests, executing the **real** function extracted from both files under `node`. Negative
controls assert `signed_off` and `not_needed` stay undispatchable. A twin test asserts both
drivers carry an identical predicate — the defect was in both, and fixing one is not fixing
the other.

### Still open

No cross-drive attempt counter, so an unfixable phase is retried once per re-drive
(operator-gated). `build-ticket.js:902`'s `noPhaseRequired` message still advises *"Do not
look for a failed phase"* — now much harder to reach, but still wrong if reached.
