---
title: "Ticket Close — Every Route to the Finished State"
description: "L3 sequence diagram of the ticket close: from the moment a drive decides a ticket is finished to the moment its recorded state changes. Names every participant that can write the finished state, shows both drivers reaching the same checking mechanism, shows the mechanism deciding from the record it read rather than from what the caller passed it, and draws the refusal and the blanket override as their own paths. Exactly one path in the close ends in the finished state being written, and it passes through the mechanism."
type: architecture
diagram_type: sequence
flight_level: L3-Component
status: active
created: 2026-09-23
last_updated: 2026-09-23
components:
  - build_orchestration
  - supervisor_system
parent: docs/architecture/components/build-orchestration.md
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/adrs/ADR-046-completion-demanded-set-is-record-only.md
  - docs/architecture/adrs/ADR-047-single-writer-ticket-close-path.md
  - docs/architecture/adrs/ADR-048-order-independent-per-ticket-completion.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/known-issues/build-orchestration.md
related_code:
  - scripts/set_ticket_status.py
  - templates/agents/status-checker.md
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/finalize-feature.js
source_ticket: tickets/00_inbox/epics/EPIC-WorkIsOnlyEverMarkedFinishedThroughThe/05_TICKET-20260914-BO-400e-5.md
tags:
  - ticket-close
  - single-writer
  - phantom-done
  - set-ticket-status
  - build-orchestration
---

# Ticket Close — Every Route to the Finished State

This diagram answers one question: **how many doors are there to a ticket's finished
state?** It covers the close from the moment a drive decides a ticket is finished to the
moment the recorded state changes, and it is deliberately drawn so that a route which is
not on it is a route which does not exist.

It is **derived from the records, not from the source**. The shape it depicts is the one
established by [ADR-046](../adrs/ADR-046-completion-demanded-set-is-record-only.md) (the
demanded-step set is record-only), [ADR-047](../adrs/ADR-047-single-writer-ticket-close-path.md)
(a single writer of the finished state, with the blanket override rejected as a route) and
[ADR-048](../adrs/ADR-048-order-independent-per-ticket-completion.md) (order-independent
per-ticket completion). Where this diagram and those records disagree, **the records are
right and this diagram is stale** — it must never be read as amending them.

Seven participants appear. Three of them can cause the recorded state to change; only one
of the three does so inside the close, and it is the same mechanism that performs the
check.

---

```mermaid
sequenceDiagram
    autonumber
    participant BF as build-feature.js<br/>epic driver
    participant BT as build-ticket.js<br/>single-ticket driver
    participant SC as status-checker<br/>Closing protocol
    participant CHK as scripts/set_ticket_status.py<br/>the checking mechanism
    participant REC as The ticket's own record<br/>status + agents map + Sign-offs
    participant OP as Operator<br/>explicit manual repair
    participant FF as finalize-feature.js step 3.5<br/>merge-time reconciliation

    Note over BF,FF: SCOPE — a drive decides a ticket is finished, and the recorded state changes.<br/>Every participant able to write that state is drawn. Nothing else can write it.

    rect rgb(232, 244, 255)
    Note over BF,REC: BOTH DRIVERS, ONE DERIVATION. Twins by ADR-047 §7 — same read-back,<br/>same verdict function, same dispatch, changed in the same commit.
    BF->>REC: concludeTicket — read back THIS ticket's own record
    REC-->>BF: agents map + sign-off headings
    BF->>BF: demandedPhasesFromRecord then completionVerdictFromRecord<br/>record-only; no caller-supplied list is an input (ADR-046)
    BT->>REC: concludeTicket — read back THIS ticket's own record
    REC-->>BT: agents map + sign-off headings
    BT->>BT: demandedPhasesFromRecord then completionVerdictFromRecord<br/>record-only; no caller-supplied list is an input (ADR-046)
    end

    alt PATH A — driver verdict is not-complete
        Note over BF,BT: Neither driver dispatches a close. No mechanism is invoked.
        BF-->>BF: payload marks the ticket not_completed, naming outstanding_phases
        BT-->>BT: payload marks the ticket not_completed, naming outstanding_phases
        Note over BF,REC: TERMINAL — recorded state UNCHANGED, outstanding step named.
    else driver verdict is complete — one close dispatch, unforced
        BF->>SC: writeTicketCompletion — follow your own Closing protocol
        BT->>SC: writeTicketCompletion — follow your own Closing protocol
        SC->>CHK: python3 scripts/set_ticket_status.py --ticket TICKET_PATH --status done<br/>no additional flags, no override, no other route
        CHK->>REC: read the record ITSELF — its current status and its agents map
        REC-->>CHK: current status + every agents entry
        CHK->>CHK: decide from what was read — is any agents entry still needed?<br/>The confirmed-phase list in the dispatch is NOT an input, and the<br/>script accepts no exclusion parameter (ADR-046 §2, ADR-047 §3)

        alt PATH B — the mechanism refuses
            CHK-->>SC: exit 1 — "Cannot set done - agents with status 'needed': PHASE"
            Note over CHK,REC: No write is attempted. Recorded state UNCHANGED.
            SC-->>BF: status error, carrying the outstanding step the mechanism named
            SC-->>BT: status error, carrying the outstanding step the mechanism named
            Note over BF,OP: TERMINAL — reported NOT closed. No retry, no second route,<br/>no reattempt with the override (ADR-047 §5).
        else PATH C — the mechanism accepts
            CHK->>REC: write the finished state, then stage the file
            REC-->>CHK: recorded state is now finished
            CHK-->>SC: exit 0
            SC-->>BF: status ok
            SC-->>BT: status ok
            Note over CHK,REC: THE ONE PATH IN THIS CLOSE THAT ENDS IN THE FINISHED STATE<br/>BEING WRITTEN — and it passes through the checking mechanism.<br/>Count them: one. There is no second.
        end
    end

    rect rgb(255, 238, 238)
    Note over OP,FF: ROUTES THAT EXIST BUT ARE ABSENT FROM THE ORDINARY CLOSE
    OP->>CHK: --force, for explicitly user-authorized manual repair only
    CHK->>REC: writes with the parity check AND the transition allow-list both skipped
    Note over OP,REC: Unreachable from either driver. A close that succeeds only because<br/>the override was passed is a failure of ADR-047 §3, not a close.
    end

    FF->>CHK: set_ticket_status.py --status done, per still-open ticket, at merge time
    CHK->>REC: same parity check, same allow-list, same refusal — no override
    Note over FF,REC: Was a second door until BO-400e-3-i: a raw frontmatter rewrite,<br/>ungated, in bulk. It now reaches the finished state only through PATH C.<br/>A ticket it cannot close honestly is left open and named.
```

Parent: [Build Orchestration — Epic & Ticket Dispatch Sequencing](../components/build-orchestration.md)

---

## How to count the doors

**One.** Exactly one path on this diagram ends with the finished state being written, and
it runs through `scripts/set_ticket_status.py`. Path A never reaches a writer. Path B
reaches the writer and is turned away. Path C is the door. The override reaches the writer
only with its checks disabled and is unreachable from either driver; finalization reaches
the finished state only by going through Path C.

The count needs no qualifier, and that is recent. When this diagram was first drawn the
answer was **two** — finalization rewrote the frontmatter itself — and the count had to be
scoped to "inside the close" to read as one. That scoping was honest but it was also the
tell: a criterion that only holds once you narrow it is a criterion that does not hold.
`BO-400e-3-i` closed the second door rather than narrowing the question, and the count is
now one unconditionally.

Stating it here rather than leaving a reader to tally lifelines is the point: a diagram
that a second door could be quietly added under, without contradicting anything drawn,
would have failed at the one job this one exists for.

## What each path guarantees

1. **Both drivers derive the verdict from the record, and only from the record.** Each
   driver re-reads the ticket it is about to close and computes the demanded-step set with
   `demandedPhasesFromRecord()`, whose sole source is that ticket's own `agents:` map and
   its own sign-off headings. A ticket-planner reply, a request payload, or any other
   caller channel can neither add to nor subtract from that set
   ([ADR-046](../adrs/ADR-046-completion-demanded-set-is-record-only.md)). Because the
   inputs are the record alone, the verdict is also order-independent across a batch
   ([ADR-048](../adrs/ADR-048-order-independent-per-ticket-completion.md)).

2. **Both drivers reach the same mechanism, by the same instruction.** `build-feature.js`
   and `build-ticket.js` each dispatch `status-checker` with the same completion-write
   step, naming `scripts/set_ticket_status.py` as the route and forbidding both a direct
   record edit and the override. `status-checker` holds the single canonical closing
   procedure; the drivers route to it rather than restating a write recipe of their own
   ([ADR-047](../adrs/ADR-047-single-writer-ticket-close-path.md) §2, §6). The twins are
   drawn side by side here precisely so a reader can check whether they have diverged —
   they are required to change in the same commit ([ADR-047](../adrs/ADR-047-single-writer-ticket-close-path.md) §7),
   and a one-sided landing would be visible on this diagram as two different arrows into
   `CHK`.

3. **The mechanism decides from what it read, not from what it was handed.** The dispatch
   tells `status-checker` which phases the driver already confirmed, but that list travels
   no further. `set_ticket_status.py` opens the ticket, re-reads its `agents:` map through
   its own needed-agents scan, and refuses while any entry is still unaccounted for. It
   exposes no exclusion parameter, and introducing one — even a narrower one — is
   forbidden as the caller channel wearing a different name
   ([ADR-047](../adrs/ADR-047-single-writer-ticket-close-path.md) §3).

4. **A refusal is a terminal state with its own shape.** On a non-zero exit the record is
   left exactly as found, the refusal names the outstanding step, and the driver reports
   that ticket as not closed in the structured payload it returns. The run does not report
   success, does not retry through another route, does not retry with the override, and
   does not continue silently
   ([ADR-047](../adrs/ADR-047-single-writer-ticket-close-path.md) §5). Path A is the same
   terminal state reached one step earlier, before any mechanism is invoked.

5. **The blanket override exists, and is off the close.** `--force` disables the parity
   check and the lifecycle transition allow-list together, so it is not a surgical
   exception. It is drawn because it is real, and it is drawn outside the close because no
   driver may reach it. It remains available only for explicitly user-authorized manual
   repair of a mis-recorded ticket.

## The route that was drawn in red

`finalize-feature.js` step 3.5 also writes the finished state, at merge time, over every
ticket of the branch whose status is not already finished. Until `BO-400e-3-i` it did so by
**replacing the frontmatter status line directly** and writing the file back — no
`scripts/set_ticket_status.py`, so no parity check, no transition validation, and no
refusal between that bulk edit and the finished state. Under
[ADR-047](../adrs/ADR-047-single-writer-ticket-close-path.md) §1 — *"No other agent,
script, workflow step, or prompt MUST write that value by any other means"* — that was a
second door, and closing it had not been in scope for `BO-400e-1` through `BO-400e-4`,
which addressed the two drivers.

It now invokes the mechanism like everything else: a non-zero exit leaves the ticket open
and names it, and `--force` is explicitly forbidden there, so a refusal cannot be converted
into a close. The route is still drawn, because it is still a participant that reaches the
recorded state — but it reaches it through PATH C, which is why the count below is one.
Filed as
[`KI-BO-20260923-0630`](../../known-issues/build-orchestration/open-high-ki-bo-20260923-0630.md),
now resolved by `BO-400e-3-i`.

Worth keeping in view: this was found by drawing the diagram, not by the four
implementation tickets or their tests. AC-2's completeness clause — every writer must
appear, so that a route which is not drawn is a route which does not exist — is what forced
the enumeration that surfaced it. Correctness checks find wrong things; only a completeness
requirement finds missing ones.

A dormant third claim sits in `templates/agents/ticket-supervisor.md`, whose Constraints
section still names "flipping `status: todo` to `status: done`" as a write surface it
owns. It is not drawn as a live route because
[ADR-006](../adrs/ADR-006-flatten-supervisor-chain.md) flattened the supervisor chain and
neither driver dispatches `ticket-supervisor` for phase execution any more — but a future
change that revives that agent revives an ungated writer with it.

## Discoverability note

The house home for driver sequence diagrams,
`docs/architecture/agent_delivery_workflows.md`, already stands far over the doc-length
ratchet, and that gate refuses any growth in a file already past its limit — including a
one-line cross-link. This diagram therefore lives in `docs/architecture/diagrams/`
alongside its siblings, and **a reader arriving from `agent_delivery_workflows.md` will
not find a link to it there.** That is a real discoverability gap, forced by the ratchet
and stated here rather than left silent. The link from
[Build Orchestration](../components/build-orchestration.md) is the supported way in.

## Cross-References

- [Build Orchestration — Epic & Ticket Dispatch Sequencing](../components/build-orchestration.md) —
  the component that owns both drivers and the close they perform; the parent of this diagram.
- [ADR-046 — The Completion Decision's Demanded-Step Set Is Record-Only](../adrs/ADR-046-completion-demanded-set-is-record-only.md) —
  governs *which phases are checked*: the input to the decision drawn here.
- [ADR-047 — The Finished State Is Written Only by the Mechanism That Checks It](../adrs/ADR-047-single-writer-ticket-close-path.md) —
  governs *which mechanism may write*: the single door this diagram counts.
- [ADR-048 — Order-Independent Per-Ticket Completion](../adrs/ADR-048-order-independent-per-ticket-completion.md) —
  why a batch reaches the same verdict for the same record regardless of reach order.
- [ADR-006 — Flatten Supervisor Chain](../adrs/ADR-006-flatten-supervisor-chain.md) —
  why the two workflow drivers, and not `ticket-supervisor`, are the participants drawn.
- [`docs/known-issues/build-orchestration.md`](../../known-issues/build-orchestration.md) —
  `KI-BO-20260831-1932`, the split outcome (one refusal, two writes, one condition) that
  this diagram exists to make impossible to misread.
- [`KI-BO-20260923-0630`](../../known-issues/build-orchestration/open-high-ki-bo-20260923-0630.md) —
  the second writer this diagram itself surfaced (`finalize-feature.js` step 3.5 sub-step C),
  now resolved by `BO-400e-3-i`, which routes that step through the mechanism. The count
  below is one because of that fix, not in spite of it.
- [Documentation Coverage — Runtime Phase Flow Sequence](c3-004-documentation-coverage-phase-flow-sequence.md) —
  a sibling L3 sequence covering the pre-commit documentation gate in the same drive.

## Changelog

- **2026-09-23** — Created for `BO-400e-5`. Depicts the close path established by
  `BO-400e-1` through `BO-400e-4` and recorded in ADR-046, ADR-047 and ADR-048. Records
  `finalize-feature.js` step 3.5 as a second writer of the finished state that does not
  pass through the checking mechanism.
