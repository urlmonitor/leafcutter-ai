---
title: "KI-BO-028 — Six `done` acceptance criteria in this component are falsified by defects already recorded in this register"
description: "KI-BO-028 — Six `done` acceptance criteria in this component are falsified by defects already recorded in this register"
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

# KI-BO-028 — Six `done` acceptance criteria in this component are falsified by defects already recorded in this register

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Numbered 028, not 025.** This entry was authored as `KI-BO-025` against an `origin/main`
> that had no 025, and collided on rebase with the 025/026/027 another session landed in the
> interval — a fresh instance of `KI-BO-024`, caught by a merge conflict rather than by any
> check, which is the whole of that entry's argument. Renumbered here along with its four
> inbound references. Counted as `KI-BO-024`'s occurrence, not filed separately.

- **Severity:** high
- **Status:** open — handover ticket raised, not started
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `BP-600e-2`, `BO-2400f-3`, `BO-2400e-4`, `BO-2200c-5`, `BO-202`, `BO-2300a-1`, `BO-2300a-2`, `BO-1500f-1` — and `unit_tests/workflows/test_fast_lane_ship_structure.py:289`, the test that let three of them read `done`

**Ticket:** [`tickets/00_inbox/TICKET-20260825-BuildOrchestrationPhantomTriage.md`](../../tickets/00_inbox/TICKET-20260825-BuildOrchestrationPhantomTriage.md)

**Symptom.** A read-only triage on 2026-08-25 walked all 65 entries across five
known-issues registers and asked, per entry, whether an acceptance criterion already covered
it. For this component the answer was repeatedly *yes, and the AC is marked done while the
criterion it states is false*. The full evidence per record is in the ticket; this entry
exists so the finding is reachable from the register rather than only from a PR body.

**This entry is a handover.** It was raised from outside this component's work queue. The
owner should re-scope, split or reject any of it — nothing in the ticket was written by
someone holding the context that produced these records.

**The mechanism is worth more than the list.** Three of the six were held up by
**presence-only assertions over JavaScript source**. `BO-2400f-10`'s entire covering evidence
was `self.assertIn("release", content)`, which passes while all eleven release dispatches go
to an agent that refuses the role; its behavioural tests call `release_claim` directly, so the
function works and its caller is dead. `KI-BO-008` files this mechanism in its own right, and
`BP-1100b-5` (`work_status: todo`) already specifies the guard that would catch it — its
scanned-source globs already include `templates/workflows-js/**/*.js`. **Building `BP-1100b-5`
and running it retroactively over existing stock would have caught three of the six**, which
makes it the highest-leverage item and arguably the thing to do before the individual repairs.

**Two were already handled and are excluded.** `BO-2400f-10` and `BO-2400c-1-iii` moved from
`done` to `in_progress` while the triage was running. Re-check the rest the same way before
starting; this register moves fast enough that a day-old finding is worth re-verifying.

**Corrections to existing entries, found during the same pass.** Recorded here rather than
edited into each entry, because this triage did not own them:

- **`KI-BO-011`** says the class — an unreachable file serving as a criterion's proof — "has no
  AC and is the reason this entry stays open". `BO-2900a-3` ("Code that no way of running the
  product can reach cannot be marked done, however many tests pass") specifies it precisely and
  is `todo`, `readiness: reviewed`. The entry's own fix direction said to check the `BO-2900`
  family first; that check was not done.
- **`KI-BO-011`**'s evidence line — "`BO-2500d-1` also names the orphan in its `implemented_by`"
  — is stale since 2026-08-19; that field now points at `fast-lane-ship.js`.
- **`KI-BO-013`**'s headline, "`test_required: false` is honoured by nothing", is overstated.
  `check_done_proof.py` honours it in two places and backs the required CI gate. The body's
  narrower claim — that the *fast lane's* chain is blind to it — is correct and is what was
  verified.
- **`KI-BO-014`** calls `BO-2600a-5` "another phantom-done instance". It is not: every `Then`
  clause in that record sits inside the `--ids` scenario and the final clause explicitly scopes
  `--ac` out, so the record is satisfied by its own wording. The real finding is weaker and more
  common — a hygiene rule written as a scenario-scoped clause when it should have been
  unconditional. Calling it phantom-done makes the fix look like a reconciliation when it is an
  amendment.
- **`KI-BO-012`**'s status line reads "open — no AC" while its own body discusses `BO-2400d-3`
  and `BO-2400d-1-i` as done ACs. Four ACs exist; the problem is that all four open with a
  `Given` presupposing that telemetry is already being recorded, so none can be falsified by
  zero emission.
- **Stale line numbers.** PR #541 shifted `fast_lane.py`. `KI-BO-022`'s `:169-171`/`:205-207`
  are now `:266`/`:186`; `KI-BO-023`'s `:180-185`/`:289`/`:347`/`:462` are now
  `:281`/`:380`/`:438`/`:553`. Both defects are unchanged — only the addresses moved.

**Not everything was still broken**, which is worth saying in a register that only ever
accumulates: `KI-BO-007` is largely discharged — `build-feature.js` now has a real read-back
adjudication that fails closed — and `KI-BO-016`'s filed N+1 defect is genuinely fixed by an AC
whose criteria is a parse-count assertion rather than a wall clock, which is the right shape.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M1 (a test that greps for a string
instead of exercising the behaviour) is the dominant one here; `KI-CG-001`'s population-vs-change
scoping is the dominant one in the sibling registers.

**Addendum 2026-08-26 — a nineteenth phantom-done, and a further concentration.**

`BO-1000c-1a` ("background finalize appends each progress line to a durable, pollable
run-progress journal as it happens") is the nineteenth phantom-done attributed to this sweep,
and the first of them to be **closed**: fixed and merged 2026-08-26 as PR #573, squash
`d97eb399`. `appendJournal()` called `require('fs')`, but the E2 engine injects no module
loader (ADR-030), so the call threw on every invocation inside a `try`/`catch` that logged a
WARNING while the run reported success. The AC read `work_status: done` throughout. The helper
and both call sites are removed; the criterion was redefined onto the journal the engine
already writes per agent dispatch; `work_status` is now `in_progress`, not `done`, because
only 1 of its 5 declared test descriptors is implemented.

The count is the sweep's own accounting, not a field any register maintains — its findings are
spread across this entry, `KI-ACD-019`, and the reopened-AC changelogs, and no single list
holds all of them. Recorded here because this entry is the closest thing the register has to
that list.

**A note on the count.** Earlier drafts of this addendum said "this entry names three"
concentrations and called the new one the fourth. It does not: this entry names **one**
mechanism plus a closing Pattern line, and `BO-2200c-5` appears only in a **Where** list. The
taxonomy of three — presence-only assertions over JavaScript source (M1), population-vs-change
scoping (`KI-CG-001`), and a producer never round-tripped through its consumer
(`BO-2200c-5`) — comes from the 2026-08-25 triage's own working notes, not from this register,
and counting a fourth against a set this entry never stated was retro-fitting.

Stated properly: `BO-1000c-1a` exhibits a concentration **not among those three**, filed as
**`KI-BO-20260826-1333`** — a test file where nine of ten tests are presence-only against one
source file, so the shape is close to the file's whole design rather than one weak test among
stronger ones, and the AC looked comprehensively covered precisely because coverage was
measured by count. Nine of the ten fail against the corrected source, each demanding the dead
mechanism be restored; the tenth, an absence assertion, survives. Its countermeasure — a single
**absence** assertion, which a behavioural test cannot substitute for when the reintroduction
is inert — is recorded there.

---
