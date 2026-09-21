---
title: "EPIC: A guard that has never said no is not counted as protection"
epic_name: EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs
created: 2026-09-14
status: in_progress
components:
  - commit_guardian
  - precommit_hooks
source_ac: GE-120f
depends_on: []
change_target: code
risk_surface: contract_boundary
# Considered, not needed. No new component is introduced -- the runner and the
# registration gate join the existing commit-guardian family, whose C4 diagram
# already covers it. GE-120f-1's own doc_links carry the per-ticket diagram
# question; this is the epic-level answer, not a deferral of theirs.
requires_diagram: false
# Considered, not needed. The decision this epic encodes -- a check declares what
# it must refuse, and a declaration is not a demonstration -- is written as an
# enforced rule by GE-120f-4 and as the procedure authors read by GE-120f-5, which
# is the tree's own chosen mechanism. An ADR restating it would be a second place
# for the rule to drift from the gate, which is the failure GE-120f-5 exists to
# prevent.
requires_adr: false
---
# EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs

## Goal

This epic implements AC GE-120f: A guard that has never said no is not counted as protection. Tickets 01-09 were generated from the leaf ACs beneath GE-120f; tickets 10-16 from the leaf ACs beneath GE-129a, which extend the same liveness run to the session-hook surface. Sixteen tickets, assembled in topological build order. Inter-ticket dependencies are derived from the AC `depends_on` graph except where the Dependencies section below records otherwise.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260914-GE-120f-1.md](./01_TICKET-20260914-GE-120f-1.md) | A check's refusal is established by putting its declared known-bad input through the entry point the protected surface uses, and the record says what was observed rather than what was declared | GE-120f-1 | — |
| 02 | [02_TICKET-20260914-GE-120f-1-i.md](./02_TICKET-20260914-GE-120f-1-i.md) | A refusal produced by reaching inside a check is not a demonstration — the run states the entry point it used, and only the entry point the protected surface invokes counts | GE-120f-1-i | 01_TICKET-20260914-GE-120f-1.md |
| 03 | [03_TICKET-20260914-GE-120f-1-ii.md](./03_TICKET-20260914-GE-120f-1-ii.md) | A check that also refuses the work it is meant to accept has demonstrated nothing — refusing everything is as inert as refusing nothing, and is reported under its own wording | GE-120f-1-ii | 01_TICKET-20260914-GE-120f-1.md |
| 04 | [04_TICKET-20260914-GE-120f-2.md](./04_TICKET-20260914-GE-120f-2.md) | A check whose declared rejection was not observed is named and fails the run, and a check that has never been asked to refuse is never counted among the things keeping the work safe | GE-120f-2 | 01_TICKET-20260914-GE-120f-1.md |
| 05 | [05_TICKET-20260914-GE-120f-2-i.md](./05_TICKET-20260914-GE-120f-2-i.md) | The finding is the run's own outcome, never a note printed beside a success — and a run that could not reach a verdict is unresolved rather than either | GE-120f-2-i | 04_TICKET-20260914-GE-120f-2.md |
| 06 | [06_TICKET-20260914-GE-120f-3.md](./06_TICKET-20260914-GE-120f-3.md) | The liveness run states how many checks it actually put an input through, that figure moves when the population moves, and a run that put an input through none fails as unresolved | GE-120f-3 | 01_TICKET-20260914-GE-120f-1.md |
| 07 | [07_TICKET-20260914-GE-120f-4.md](./07_TICKET-20260914-GE-120f-4.md) | A check joins the protected family only by declaring what it must refuse, read from where it is registered — so the next check inherits the requirement by existing rather than by someone remembering | GE-120f-4 | — |
| 08 | [08_TICKET-20260914-GE-120f-4-i.md](./08_TICKET-20260914-GE-120f-4-i.md) | A check that was already registered when the requirement arrived is subject to it identically, and a ground that is a fact about when a check was registered is no ground at all | GE-120f-4-i | 07_TICKET-20260914-GE-120f-4.md |
| 09 | [09_TICKET-20260914-GE-120f-5.md](./09_TICKET-20260914-GE-120f-5.md) | The rule is written where the next check author is already looking, in the vocabulary the machine reads, and the written procedure and the enforced procedure say the same thing | GE-120f-5 | 01_TICKET-20260914-GE-120f-1.md, 07_TICKET-20260914-GE-120f-4.md |
| 10 | [10_TICKET-20260921-GE-129a-1.md](./10_TICKET-20260921-GE-129a-1.md) | What is examined is a place a guard is invoked from, not a script — the same guard wired at two tool-call events is two things to prove, and a guard the settings surface does not name is not this run's business | GE-129a-1 | 01_TICKET-20260914-GE-120f-1.md |
| 11 | [11_TICKET-20260921-GE-129a-2.md](./11_TICKET-20260921-GE-129a-2.md) | A session guard's declaration of what it must refuse is tied to the entry that runs it by particulars read from the surface, so an entry that moves out from under its declaration leaves the guard undeclared instead of quietly keeping the credit | GE-129a-2 | 10_TICKET-20260921-GE-129a-1.md |
| 12 | [12_TICKET-20260921-GE-129a-3.md](./12_TICKET-20260921-GE-129a-3.md) | The input arrives as the tool call the guard actually sees, and the refusal counted is the tool call not happening — a rejection the event it is wired to cannot produce is unusable rather than satisfied | GE-129a-3 | 10_TICKET-20260921-GE-129a-1.md |
| 13 | [13_TICKET-20260921-GE-129a-3-i.md](./13_TICKET-20260921-GE-129a-3-i.md) | A guard started as a plain command with a path among its arguments, reading nothing and exiting cleanly, has been asked nothing — that clean exit is never reported as a demonstration | GE-129a-3-i | 12_TICKET-20260921-GE-129a-3.md |
| 14 | [14_TICKET-20260921-GE-129a-4.md](./14_TICKET-20260921-GE-129a-4.md) | The guard this epic keeps citing is examined on the real surface, in the copy the entry that runs it actually resolves to, and is reported as never having refused anything — beside a guard on the same surface that has | GE-129a-4 | 10_TICKET-20260921-GE-129a-1.md, 11_TICKET-20260921-GE-129a-2.md, 12_TICKET-20260921-GE-129a-3.md |
| 15 | [15_TICKET-20260921-GE-129a-4-i.md](./15_TICKET-20260921-GE-129a-4-i.md) | A guard is examined in the linked working copy the drives actually run in as well as in the main one, and a refusal seen in one layout never stands for the other | GE-129a-4-i | 14_TICKET-20260921-GE-129a-4.md |
| 16 | [16_TICKET-20260921-GE-129a-5.md](./16_TICKET-20260921-GE-129a-5.md) | Someone wiring a new guard into the editor's own tool calls, following only the written instructions, ends up with one the run reports as declared and examined — and the step they skip is the one the run names | GE-129a-5 | 11_TICKET-20260921-GE-129a-2.md, 12_TICKET-20260921-GE-129a-3.md |

Tickets 10-16 implement the GE-129a leaves — the session-hook half of the same liveness
run. They were generated separately and added to this epic rather than to one of their
own, because ADR-045 §4 fixes a single runner
(`templates/scripts/commit_guardian/check_negative_controls.py`) for both surfaces: the
commit-guardian population GE-120f sweeps and the session population GE-129a adds. Two
epics would have meant two branches editing that one file.

## Dependencies

```
GE-120f-1 (no dependencies)
GE-120f-1-i -> GE-120f-1
GE-120f-1-ii -> GE-120f-1
GE-120f-2 -> GE-120f-1
GE-120f-2-i -> GE-120f-2
GE-120f-3 -> GE-120f-1
GE-120f-4 (no dependencies)
GE-120f-4-i -> GE-120f-4
GE-120f-5 -> GE-120f-1, GE-120f-4

GE-129a-1 -> GE-120f-1        (build order, not an AC edge — see note below)
GE-129a-2 -> GE-129a-1
GE-129a-3 -> GE-129a-1
GE-129a-3-i -> GE-129a-3
GE-129a-4 -> GE-129a-1, GE-129a-2, GE-129a-3
GE-129a-4-i -> GE-129a-4
GE-129a-5 -> GE-129a-2, GE-129a-3
```

The `GE-129a-1 -> GE-120f-1` edge is not in the AC `depends_on` graph. GE-129a-1's only
declared dependency is its parent composite GE-129a, which has no ticket. The edge is
taken from GE-129a-1's `it_requirements`, which state that the session population "is
registered behind GE-120f-1's RUNNER, NOT BESIDE IT" — so the runner must exist before
the reader can be registered against it. Without this edge the two would be schedulable
in parallel and ticket 10 would have nothing to register into. Every other GE-129a ticket
reaches GE-120f-1 transitively through it.

The `GE-129a-3-i -> GE-129a-3` and `GE-129a-4-i -> GE-129a-4` edges are in the AC graph
but were dropped by the ticket generator, which filters parent edges out of `depends_on`
— and for a Roman-suffixed constraint record the dependency *is* the parent. They were
restored by hand.

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 14, 15 |
| ac-validator | 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 14, 15 |
| architect-review | 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 14, 15 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| documentation-expert | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| documentation-verifier | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| llm-expert | 09 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 14, 15 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16 |

Tickets 09 and 16 are the two documentation tickets and both carry
`ac-fulfillment-gate: not_needed` and `ac-validator: not_needed` as generated. That is
the epic's existing posture for a docs ticket, left as-is rather than changed on one of
the pair — but it means neither ticket's AC store fields (`work_status`,
`implemented_by`, `covered_by`) are reconciled by a gate, on an epic whose subject is
checks that report success without having looked. Reconcile GE-120f-5 and GE-129a-5 by
hand before the epic is called done, or turn both gates on together.

