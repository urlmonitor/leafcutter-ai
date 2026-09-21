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

This epic implements AC GE-120f: A guard that has never said no is not counted as protection. It consists of 9 ticket(s) generated from the leaf ACs beneath GE-120f, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

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
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04, 05, 06, 07, 08 |
| ac-validator | 01, 02, 03, 04, 05, 06, 07, 08 |
| architect-review | 01, 02, 03, 04, 05, 06, 07, 08 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| documentation-expert | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| documentation-verifier | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| llm-expert | 09 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09 |

