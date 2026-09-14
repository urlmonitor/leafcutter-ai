---
title: "ADR-044: The Completion Decision's Demanded-Step Set Is Derived Solely From the Ticket's Own Record"
description: "The set of phases a ticket's close is checked against MUST be read out of the ticket's own agents: map and from nowhere else, because a guard that accepts the driven party's account of which phases do not count has stopped checking that party."
type: "adr"
status: "active"
created: "2026-09-14"
last_updated: "2026-09-14"
deciders:
  - BrainCandy
components:
  - build_orchestration
  - supervisor_system
related_docs:
  - docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400a-2-i.yaml
  - docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400a-2-ii.yaml
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/components/build-orchestration.md
  - docs/known-issues/build-orchestration.md
related_code:
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - scripts/set_ticket_status.py
  - unit_tests/prompt_assembly/harness_build_ticket_guard.mjs
---

# ADR-044: The Completion Decision's Demanded-Step Set Is Derived Solely From the Ticket's Own Record

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-14 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded during the `BO-400e-1` demanded-set pass of 2026-09-14 |
| Supersedes | None |

## Context

A ticket is closed — written to `status: done` — at the completion-write step of the two
workflow drivers, `templates/workflows-js/build-feature.js` (epic drives) and
`templates/workflows-js/build-ticket.js` (single-ticket drives). These two are the only
surfaces that reach the completion write;
[ADR-006](ADR-006-flatten-supervisor-chain.md) is why, having flattened the supervisor
chain so the drivers, not an intermediate `ticket-supervisor`, own dispatch and closure.
They declare each other twins in their own file headers, a standing constraint of
[`BO-400a-2-ii`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400a-2-ii.yaml).

Before writing `done`, each driver computes a **demanded-step set**: the phases whose
sign-offs the close is checked against. Today that set is produced by
`requiredPhasesForCompletion(drivenPhases, recordNeededPhases, deferredPhases)`, present
in identical hand-duplicated form in both files. It is a **union** of `drivenPhases` — the
list the *calling drive* hands in, describing what it was asked to run — with
`recordNeededPhases`, read from the ticket's own frontmatter `agents:` map, minus
`deferredPhases`, a caller-supplied exclusion list. Two of the three inputs therefore come
from the party whose behaviour the guard exists to check.

The cost of not deciding is already on the record.
`KI-BO-20260831-1932` in [`docs/known-issues/build-orchestration.md`](../../known-issues/build-orchestration.md)
documents a single drive in which three tickets sat in *exactly* the same state — every
phase signed off except `pull-request: needed`, with no sign-off entry for it — and the
guard **refused** ticket 01 while **flipping tickets 03 and 20 to `status: done`**. Both
paths received the same eight-item request; only one of them went and read the ticket for
a ninth. The lenient write was a phantom-done: it recorded `done` on a ticket the guard's
own stated rule says is not done, and ticket 20's write then had to be caught downstream
by `check-ticket-ac-status-parity`. Worse than the inconsistency is that a guard producing
both outcomes from one condition gives no signal about which it will produce next, so
neither result is evidence of anything. Characterising this took two readers a day, and
the two of them drew *opposite* conclusions from the same paragraph — which is precisely
why the direction belongs in a citable decision record rather than in a code comment or a
ticket constraint list.

[`BO-400e-1`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-1.yaml),
the AC this record serves, closes the question with three attempts that differ only in what
the caller presents alongside the close request — a narrowed list, a widened list, and no
list at all — and requires all three to produce the identical refusal. Each attempt closes
one reconciliation strategy: intersect, union, and fall-back. The only implementation that
passes all three never reads the caller's list.

`scripts/set_ticket_status.py`, the mechanism that performs the write, is already correct
on this point: `_get_needed_agents` reads the demanded set solely from the ticket's
`agents:` YAML map, and the script has **no** exclusion parameter. Its absence is
load-bearing, and this ADR exists in part to keep it absent.

## Decision

1. **The demanded-step set has exactly one source: the ticket's own record.** Both drivers
   MUST derive it from the ticket's frontmatter `agents:` map — every agent entry whose
   value is not `not_needed` — and from nothing else. `requiredPhasesForCompletion` in
   `templates/workflows-js/build-feature.js` and in `templates/workflows-js/build-ticket.js`
   MUST NOT read `drivenPhases`, and MUST NOT read any caller-supplied exclusion list, when
   producing the set the completion decision is taken against.

2. **No caller channel MUST be opened.** No parameter, prompt field, request payload,
   environment variable, or configuration key MUST be able to add a phase to, or remove a
   phase from, the derived set. In particular `scripts/set_ticket_status.py` MUST NOT gain
   an exclusion, skip, or override parameter; its current lack of one is the guarantee, not
   an oversight.

3. **Do not intersect, do not union, do not fall back.** The derivation MUST NOT intersect
   the caller's list with the record's, MUST NOT union them (the present defect), and MUST
   NOT consult the caller's list even when it is the only list offered. A close request that
   carries no list at all MUST produce a decision byte-identical to one that carries a
   narrowed or a widened list.

4. **Deferral MUST be expressed in the record, never in the request.** A phase that does not
   apply to a ticket — an epic member's `pull-request` phase, opened once per epic by
   `finalize-feature` — MUST be recorded as `not_needed` in that ticket's `agents:` map by
   whatever authors the ticket. The drivers MUST NOT accept a `deferredPhases` argument as
   grounds for excluding a phase the record still names as needed.

5. **Both twins MUST change in the same commit, and MUST derive identically.**
   `build-feature.js` and `build-ticket.js` MUST arrive at the same demanded-step set for
   the same ticket record. A landing in one alone is forbidden: it produces a system in
   which epic drives and single-ticket drives disagree about what a close is checked
   against, which is this same defect relocated.

6. **The decision MUST be observable per ticket.** Each run MUST record, for every ticket it
   closes or refuses, which demanded-step set it decided against and which step was found
   unaccounted for. A refusal MUST name the unaccounted phase.

7. **A refusal MUST NOT write.** When the set is not fully accounted for, the ticket's
   recorded state MUST be left exactly as found — no lifecycle status written, no `agents:`
   value altered, no sign-off synthesised.

8. **`BO-400a-2-i` and `BO-400a-2-ii` are ratified, not narrowed.** Neither the refusal rule
   nor its trigger MUST be relaxed, bounded, or given an exception in order to accommodate
   this derivation. If a change appears to require softening either, that change is wrong.

## Consequences

### Positive

- The guard regains the only property that made it worth having: it checks the driven party
  against a record the driven party did not author for this purpose. A drive can no longer
  talk its way past a close.
- The three-way split in `KI-BO-20260831-1932` becomes impossible by construction. Identical
  ticket states produce identical outcomes, so an outcome is once again evidence.
- Both drivers answer the same question the same way, so a result observed on a
  single-ticket drive predicts the epic-drive result and vice versa.
- Per-ticket observability (Decision §6) means the next divergence, if one occurs, is
  attributable in one reading rather than distinguishable from agent caprice only after a
  day of analysis.

### Negative

- Leniency disappears, and leniency was load-bearing while the records were wrong. Every
  ticket whose record still names a phase it will never receive now halts, reliably and
  permanently, instead of slipping through roughly two times in three.
- `deferredPhases` ceases to be an escape hatch. Any legitimate "this phase does not apply"
  case must now be fixed at the record, which is more work than passing an argument and
  requires the ticket generator to be correct.
- The derivation stays hand-duplicated across two files. That duplication is exactly why the
  union bug is present identically in both today, and it remains a standing divergence risk
  (see Alternatives).

### Operational

- **Sequencing is mandatory and this ADR does not license ignoring it.** Per
  `KI-BO-20260831-1930`, roughly 316 existing tickets carry `pull-request: needed` when they
  should carry `not_needed`. Landing Decision §1–§4 before those records are repaired halts
  the next drive on ticket one of 316, with 315 behind it. The mechanical repair — fix the
  generator, then sweep the tickets that already exist — MUST land first. Reading the ticket
  without correcting the ticket halts everything; correcting the ticket without reading it
  leaves a guard that trusts its caller. The two halves are a pair.
- `templates/workflows-js/*.js` are build sources, not the running artefact: the build
  deploys them into the workflow directory that actually executes. A change confirmed only
  against the source tree is not confirmed against what runs. Keep the deployed copy in step
  (`check-build-drift` is the gate) and confirm the behaviour through the deployed layout
  before sign-off.
- Conformance MUST be verified by execution, never by grep. The phase-list code, the
  completion prompt, and the parity check are all already present in the source today, so a
  test that searches for any of them passes unchanged on the broken driver. Coverage belongs
  in `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs`, which loads and runs the
  real workflow script and can assert on what a run actually wrote to the ticket record.

## Alternatives

- **Union the caller's list with the record's (the status quo).** Rejected. This is the
  present implementation and the source of the defect: a caller can widen the demanded set
  with phases the record never names, and — because the union is then reduced by a
  caller-supplied `deferredPhases` — can also narrow it. It fails `BO-400e-1`'s widened-list
  attempt outright.
- **Intersect the caller's list with the record's.** Rejected. The intersection lets any
  phase the caller omits drop out of the demanded set, which is exactly the narrowing that
  produced the phantom-done write on tickets 03 and 20. It fails the narrowed-list attempt.
- **Read the record only when no caller list is offered.** Rejected. This is the most
  plausible-looking fix and it is why `BO-400e-1` includes a third attempt with no list at
  all: the fallback passes the narrowed and widened attempts by accident while leaving the
  caller in control whenever it chooses to speak. A guard that can be switched off by
  supplying an argument is not a guard.
- **Have the completion writer trust the exclusion list its caller hands it.** Rejected
  explicitly, because it is what the obvious fix looks like. The refusal is worth something
  only while the record is authored by someone other than the party being checked; a writer
  that accepts the drive's word about which phases do not count has stopped checking the
  drive, which is the only thing it was ever for. It would fix today's symptom by deleting
  the guard.
- **Add an `--exclude-phase` (or equivalent) parameter to `scripts/set_ticket_status.py`.**
  Rejected. It reopens the caller channel one layer down: the drivers would derive the set
  correctly and then hand the write step an override, restoring caller control at the exact
  moment the record is mutated. The script's lack of such a parameter today is load-bearing.
- **Relax `BO-400a-2-i`'s refusal, or carve out an exception for deferred phases.** Rejected.
  It resolves the 316-ticket halt by making the wrong records acceptable, permanently, rather
  than by repairing them once. The halt is a true statement about those tickets; silencing a
  true statement is the phantom-done failure mode this subsystem exists to prevent.
- **Land the change in `build-feature.js` only (or `build-ticket.js` only) and follow up.**
  Rejected. The two drivers would then disagree about what a close is checked against, which
  is the same defect this decision closes, relocated to a seam that is harder to observe
  because it only appears when the same ticket is driven both ways.
- **Extract a shared `templates/workflows-js/lib/completion-decision.js` first, and make that
  extraction a precondition of this change.** Rejected as a precondition. The extraction does
  not change where the demanded set comes from — a shared module fed `drivenPhases` is just
  as wrong, in one place instead of two — and making it a gate widens the blast radius of a
  correctness fix that is already sequencing-constrained. It remains a reasonable follow-up
  for the divergence risk noted under Consequences → Negative.

## References

- Originating ticket: `tickets/00_inbox/epics/EPIC-WorkIsOnlyEverMarkedFinishedThroughThe/01_TICKET-20260914-BO-400e-1.md`
- Originating AC: [`BO-400e-1`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-1.yaml)
- Ratified, not amended: [`BO-400a-2-i`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400a-2-i.yaml) (the refusal rule),
  [`BO-400a-2-ii`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400a-2-ii.yaml) (the twin constraint)
- Known issues: `KI-BO-20260831-1932` (split outcome on identical conditions) and
  `KI-BO-20260831-1930` (the `pull-request: needed` population), both in
  [`docs/known-issues/build-orchestration.md`](../../known-issues/build-orchestration.md)
- [ADR-006 — Flatten Supervisor Chain](ADR-006-flatten-supervisor-chain.md) — why the two
  drivers, and not `ticket-supervisor`, are the surface that reaches the completion write
- [`docs/architecture/components/build-orchestration.md`](../components/build-orchestration.md) —
  the component boundary this decision stays inside
