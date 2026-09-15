---
title: "KI-BO-20260901-1000 — The per-ticket phase list is frozen before the first phase runs, so a phase that a later phase declares necessary can never be dispatched — and `architect-review`, whose job is to declare exactly that, is ordered after the phases it gates"
description: "KI-BO-20260901-1000 — The per-ticket phase list is frozen before the first phase runs, so a phase that a later phase declares necessary can never be dispatched — and `architect-review`, whose job is to declare exactly that, is ordered after"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260901-1000 — The per-ticket phase list is frozen before the first phase runs, so a phase that a later phase declares necessary can never be dispatched — and `architect-review`, whose job is to declare exactly that, is ordered after the phases it gates

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** open — no AC
- **Occurrences:** 1 run, **2 of 4 tickets in the batch** (`GE-122d-3`, `BP-900h-6`) — both halted, neither recoverable within the drive
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/workflows-js/build-feature.js` — `driveTicketPhases()` Step 2/Step 3
  (`neededPhases` computed once at ~:1345, iterated at ~:1430) · `phaseOrder` (~:305)

**Symptom.** Two independent tickets in one batch halted with the same shape: `architect-review`
ran, concluded an ADR was required, flipped `requires_adr: true` and set
`agents.adr-author: needed` — and `adr-author` was then never dispatched. `python-coder`
subsequently refused to write code against a contract that had not been recorded, which is the
correct refusal, so the drive ends with two tickets stuck behind a phase the drive itself will
never run.

**Root cause — the list is a snapshot, not a queue.** Step 2 computes the phase list exactly
once, from the planner's opening snapshot:

```js
const neededPhases = sortByCanonicalPriority(
  selectDispatchPhases(orderedPhases.filter((p) => p.status === "needed"), isEpicMember)
);
```

Step 3 then walks it:

```js
for (const currentPhase of neededPhases) {
```

`neededPhases` is never recomputed. A phase promoted to `needed` *during* the drive is
invisible to the loop, because the loop is iterating a value captured before any phase ran.

**Two orderings make this specifically unrecoverable rather than merely late.** `phaseOrder`
puts `adr-author` at priority 2 and `architecture-diagram-author` at 3, but `architect-review`
— the phase that decides whether either is needed — at 4. So even if the list *were*
recomputed, a forward-only walk would already be past both slots by the time the decision is
made. The gating phase runs after the phases it gates. Freezing the list and ordering the
decider last are two independent bugs that happen to produce one symptom; fixing either alone
leaves the other.

**The signal is computed correctly and then discarded.** This is not a case of the system
failing to notice. The driver re-reads the ticket record after each phase, and those re-reads
returned the right answer — from this run's own journal, after `architect-review` signed off:

```text
"needed_phases":["ac-fulfillment-gate","ac-validator","adr-author","commit",
                 "documentation-expert","documentation-verifier","pr-reviewer",
                 "pull-request","python-coder","test-runner","test-writer"]
```

`adr-author` is right there, named, in a value the driver received and parsed. Nothing consumes
it. The read-back exists to feed the *completion* decision, not the *dispatch* decision, and no
code path connects the two. This is the fourth recorded instance in this register of a signal
being derived accurately and then not wired into the control flow it was derived for.

**Why the phase agents look worse than they are.** Both halts were well-reasoned and both were
right. `python-coder` on `GE-122d-3` verified ADR-037's status on disk rather than from memory,
found it `Proposed` with no amendment, noted six sibling ACs already consuming the
`NamespaceVerdict` shape it would have had to narrow, and stopped. `python-coder` on
`BP-900h-6` checked that `ADR-038` did not exist and cited architect-review's explicit
sequencing instruction. `test-runner` then re-derived the same blocker independently and
confirmed the red baseline was intact under `AC_ENFORCE_STRICT=1` (7 failed, matching
test-writer's record) rather than reporting a regression. The adjudication ladder classified
correctly at every step. The agents did their jobs; the driver had no way to act on the result.

**Countermeasure.** Both halves need addressing:

1. **Re-derive the pending set each iteration** instead of iterating a frozen array — drive
   from the record's live `needed` set, so a phase promoted mid-drive is picked up. The
   re-read already happens and already carries the answer; it needs connecting to dispatch.
2. **Move `architect-review` ahead of the phases it gates** in `phaseOrder`, or give
   `adr-author` and `architecture-diagram-author` a second slot after it. A decider that runs
   after the phases conditioned on its decision cannot work under any forward-only walk.

Until then, a ticket whose `requires_adr` is flipped by `architect-review` cannot be completed
by `/build-feature` and must be finished by hand — author the ADR, then re-drive.

**Pattern:** `docs/reference/false-green-mechanisms.md` → a correctly-computed signal with no
consumer. Distinct from the phantom-done family: nothing here claims success. The drive halts
honestly and reports the blocker; the defect is that the blocker is one the drive created for
itself and cannot clear.

**Related.** `KI-BO-20260901-0920` (filed the same run — the commit-phase lock, also a control
that the runbook describes and the flattened driver does not implement; ADR-006's flattening
dropped both). `KI-ACD-020` (a readiness gate dropping leaves silently — the same
computed-then-discarded shape one layer up, in `goal_to_epic.py`).

---
