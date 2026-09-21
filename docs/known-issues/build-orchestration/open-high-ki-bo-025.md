---
title: "KI-BO-025 — `/build-feature` plans only the first ready wave, so an epic with any dependency depth cannot be driven to completion in one run"
description: "KI-BO-025 — `/build-feature` plans only the first ready wave, so an epic with any dependency depth cannot be driven to completion in one run"
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

# KI-BO-025 — `/build-feature` plans only the first ready wave, so an epic with any dependency depth cannot be driven to completion in one run

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open · ACs **BO-100e** (carry the layers) and **BO-300d** (say what was left),
  both authored 2026-08-26, both `readiness: draft` awaiting the approval gate
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/build-feature.js` — the `epic-planner` `agent()` call
  (deployed `~:2101`), and the `for (const batch of batches)` loop that consumes its output

**Symptom.** Driving the 37-ticket `EPIC-TrustThatAGreenCheckActuallyChecked`, the planner
returned 8 batches containing **17** tickets. The other 20 were never scheduled.

The dropped set is not arbitrary. Measured against the epic folder:

```text
total tickets: 37 | planned: 17 | MISSING: 20
tickets with non-empty depends_on: 20
missing set == depends_on set ?  True
planned tickets that have deps:  []
```

Every ticket carrying **any** `depends_on` was dropped; every ticket planned had none.

**Root cause — the planner is asked for one antichain and is never asked again.** Its prompt
says:

> `(2) Compute the maximal antichain of ready tickets (all depends_on met).`

At plan time no ticket is `done`, so "all depends_on met" is true only for tickets whose
`depends_on` is empty. That is a correct reading of the instruction — the planner is not
misbehaving. The defect is that this single ready-set is treated as the whole schedule: the
`agent()` call sits **outside** the batch loop, so there is no re-plan after a batch completes
and no wave 2. One invocation can therefore build at most the dependency-free tickets.

The eight "batches" are misleading here. They are the antichain split by `files_touched`
overlap — a *parallelism* split, not a dependency sequence. Seven of the eight contain a
single ticket, which reads like a dependency chain and is not one.

**Consequence.** An epic whose dependency graph is N levels deep needs N separate manual
`/build-feature` invocations, and nothing in the run says so or says how many remain. For
GE-120 that leaves the entire `b`/`d`/`e` chain — including every consumer of the `GE-120c-1`
harness — unbuilt after a run that did substantial correct work on the other 17.

**Not a false-complete, at least.** The completion guard does catch the shortfall and withholds
the "complete" verdict — but it misdescribes the cause; see KI-BO-026.

**Why it misdescribes it, found 2026-08-31 while enriching the ACs.** The run has no record of
the epic's contents at plan time that is separate from the plan. `plannedTicketPaths`
(deployed `~:2156`) is built by iterating `batches` — the comment above it calls this "the set
of work the plan was built from … the baseline the completion-time re-read is compared against,
by identity (BO-300a-5)", but under this defect the baseline is 17, not 37. The 20 dropped
tickets are therefore absent from the baseline, and at completion time `compareEpicTicketSets`
can only see them as *additions*. **KI-BO-025 and KI-BO-026 are one defect observed from two
ends**, and separating the run's *set* from the run's *schedule* is a precondition for fixing
either — not an optimisation. It also changes what BO-300a-5 (`done`) reports, so it cannot be
done quietly.

**Fix direction.** Either loop the planner until it returns an empty batch set (re-reading
frontmatter each round, which the code comment at `~:2400` already anticipates as the resume
mechanism), or have it emit the full topological schedule as ordered waves rather than one
antichain. If the single-wave behaviour is deliberate, the run must state it: report the count
of unscheduled-but-ready-later tickets and instruct the caller to re-invoke, rather than
leaving the arithmetic to whoever compares the plan against the folder.

**A test-harness precondition blocks all of it, found 2026-08-31.**
`unit_tests/_workflow_engine_harness.py::run_workflow_under_e2` takes
`label_responses: dict[str, Any]` — **one** response object per label, serialised to a flat
JSON literal and returned on every call to that label. The `epic-planner` label therefore
cannot express wave 1 followed by a *different* wave 2, and `ticket-planner` is shared across
every ticket so it cannot differentiate per-ticket replies either. Until the harness supports
sequenced per-label responses, **not one behavioural test for this fix can be written**, and
the work collapses to exactly the grep-only proof CLAUDE.md forbids. Extend the harness first.

**Pattern:** a stage that does part of the job correctly and reports no signal that the rest
exists.

---
