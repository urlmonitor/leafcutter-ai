---
title: "Build Orchestration — Epic & Ticket Dispatch Sequencing"
description: "Build orchestration: pre-dispatch sequencing gates, dependency-cycle detection, parallelism limits, file-conflict isolation, and pre-drive reachability checks."
flight_level: L3-Component
status: active
type: reference
created: 2026-07-10
last_updated: 2026-09-23
components:
  - build_orchestration
related_docs:
  - docs/architecture/adrs/ADR-046-completion-demanded-set-is-record-only.md
  - docs/architecture/adrs/ADR-047-single-writer-ticket-close-path.md
  - docs/architecture/adrs/ADR-048-order-independent-per-ticket-completion.md
children:
  - docs/architecture/diagrams/c3-fast-lane-build-loop-sequence.md
  - docs/architecture/diagrams/c3-009-ticket-close-paths-sequence.md
---

# Build Orchestration

## Overview

Build Orchestration governs how epics and tickets are dispatched to supervisors and phase agents. It sequences work before dispatch: building the dependency graph from `depends_on` (logical) and `files_touched` (physical) edges, detecting dependency cycles, enforcing parallelism limits, isolating file-conflicting tickets into serial batches, and running pre-drive reachability checks (e.g. telemetry sink writability) before a drive begins.

## Responsibilities

- Compute the maximal next-ready ticket batch that is parallel-safe under both logical and physical edges
- Detect and surface dependency cycles before dispatch
- Enforce parallelism limits and file-conflict isolation across concurrent supervisors
- Run pre-drive reachability / precondition checks before starting an epic drive

## Entry Points

- `templates/workflows-js/build-epic.js` — epic dispatch workflow

## Integration

Build Orchestration sits above the supervisor spawn topology: it decides *what* to dispatch and in *what order*, then hands each ready ticket to a `ticket-supervisor`. See `docs/architecture/components/build-epic-workflow-dispatch.md` and `docs/architecture/components/supervisor-spawn-topology.md` for the dispatch mechanics it drives.

## Interactive Pause/Resume Diagrams

The workflow engine files owned by this component (`templates/workflows-js/plan-feature.js`
and `templates/workflows-js/finalize-feature.js`) implement the ADR-024 interactive
pause/resume substrate via the inline `resolveGate()` helper. When an interactive gate is
reached headless, the run pauses and persists a durable, run-keyed pending-question record
instead of silently cancelling; a later re-invocation resumes past the gate. The
[Interactive Pause/Resume Substrate — Container Overview](interactive-pause-resume-substrate.md)
is the L2 container for this mechanism, and the two diagrams below document it:

- [Interactive Pause/Resume — Run Lifecycle State Diagram](../diagrams/c3-001-interactive-pause-resume-run-lifecycle.md) — the run lifecycle states (`running`, `paused_awaiting_input`, `resumed`, `cancelled`, `completed`) and the `resolveGate` resume outcomes (`nothing_to_resume`, `unresumable_stale`), showing that `paused_awaiting_input` and `cancelled` are distinct and only `paused_awaiting_input` is resume-eligible.
- [Interactive Pause/Resume — Pause, Ask, Answer, Resume Sequence](../diagrams/c3-002-interactive-pause-resume-sequence.md) — the message-level interaction between the workflow engine, the agent-mediated persist/read agent, the durable store, and the answerer, including the wrong-shape re-prompt loop and cross-process resume via `resumeFromRunId`.
- [ADR-024 — Interactive Gates Pause and Persist Instead of Cancelling When Headless](../adrs/ADR-024-interactive-pause-resume.md) — the design of record.

## Occupied Build Workspace — Refuse, Do Not Reuse

When the fast lane resolves a build workspace that is already occupied — by its own earlier
attempt or by anything else — the run ends in a **named refusal** carrying the criterion, the
occupied location, and options whose destructiveness is stated separately, so that clearing
empty residue and discarding unsaved work are never the same gesture. It does **not** silently
reuse the workspace, and it does **not** bring one up to date first.

Both of those apparent kindnesses break a promise: a reused workspace is cut from a stale
mainline, so the run returns a green result built against code that has moved, and refreshing
it breaks `BO-2400f-3`'s guarantee that the workspace comes from the latest mainline. The
accepted cost is that a re-run against the same criterion needs an operator decision.

- [ADR-039 — The Fast Lane Refuses an Occupied Workspace Rather Than Reusing It](../adrs/ADR-039-fast-lane-occupied-workspace-refusal.md) — the design of record, including the rejected alternatives and the conditions under which this should be revisited.

## Phantom-Done Prevention — Real-Effect / Real-Intent Verification

The drive and verification-phase routing this component owns is where the BP-1100f
phantom-done-prevention gates plug in. Those gates prove that a durable change actually
happened by its **real effect** and **stated intent**, rather than by **dispatch
topology** (the presence, labels, or counts of dispatched helpers a test mock controls) —
the BO-2300 failure mode in which a feature was signed off twice while its real behaviour
was absent. The sequence diagram below places each of the five gates on the timeline
relative to dispatch and to the done state:

- [Phantom-Done Prevention — Proving a Durable Change by Real Effect and Intent](../diagrams/c3-003-phantom-done-real-effect-intent-verification.md) — the end-to-end BP-1100f verification flow: pre-dispatch intent-vs-surface consistency (BP-1100f-3), instruction-carrying dispatch review (BP-1100f-1), the harness-level instruction-less-dispatch contract violation (BP-1100f-4), the real-artifact test-evidence requirement (BP-1100f-2), and the automatic observable-side-effect smoke check that gates the done state (BP-1100f-5).

## Completion Decision — Demanded-Step Set Is Record-Only

The two workflow drivers this component owns, `templates/workflows-js/build-feature.js`
(epic drives) and `templates/workflows-js/build-ticket.js` (single-ticket drives), are the
only surfaces that write a ticket's `status: done`. Before doing so, each derives a
**demanded-step set** — the phases the close is checked against — via
`demandedPhasesFromRecord()` and `requiredPhasesForCompletion()`. Per
[ADR-046](../adrs/ADR-046-completion-demanded-set-is-record-only.md), that set has exactly
one source: the ticket's own frontmatter `agents:` map and its own sign-off headings. No
caller-supplied list — from a ticket-planner reply, a request payload, or any other
channel — may add to or subtract from it, and `scripts/set_ticket_status.py` (the mechanism
that performs the write) accepts no exclusion parameter for the same reason. Both drivers
must derive the set identically, in the same commit, per `BO-400a-2-ii`'s twin constraint.

`docs/known-issues/build-orchestration.md`'s `KI-BO-20260831-1932` documents the defect this
rule closes (a caller-trusted union let the same ticket state produce a refusal or a
phantom-done write depending on what the caller supplied) and includes a sequence diagram of
the corrected, record-only decision path.

## Completion Write — One Door, and It Is the One That Checks

ADR-046 governs *which phases are checked*; [ADR-047](../adrs/ADR-047-single-writer-ticket-close-path.md)
governs *which mechanism may write*. `scripts/set_ticket_status.py` is the only writer of a
ticket's finished state on the close path: both drivers dispatch `status-checker`, which
invokes that script unforced, and the script re-reads the ticket's own `agents:` map and
refuses — leaving the record exactly as found — while any entry is still unaccounted for.
A refusal is reported as *not closed*; it is never retried through another route and never
retried with `--force`, which disables the parity check and the transition allow-list
together.

- [Ticket Close — Every Route to the Finished State](../diagrams/c3-009-ticket-close-paths-sequence.md) —
  the close-path sequence: both drivers reaching the same mechanism, the mechanism deciding
  from the record it read rather than from what the caller passed it, the refusal and the
  blanket override drawn as their own paths, and the single path that ends in the finished
  state being written. The diagram also records `finalize-feature.js` step 3.5 as a second
  writer of that state which does not pass through the mechanism.

## Documentation Coverage — Runtime Phase Flow

On doc-required (v2) tickets, this component sequences two documentation phases into the
drive: `documentation-expert` (priority 10) authors the docs after the coder and test
phases, and `documentation-verifier` (priority 11.9) is the last gate before `commit` — it
asserts the required docs against the ticket's `## Agent Contracts` → `### documentation-expert`
brief and fails closed (blocking the commit) when a required doc is missing or placeholder.

- [Documentation Coverage — Runtime Phase Flow Sequence](../diagrams/c3-004-documentation-coverage-phase-flow-sequence.md) — the ordered `coder → test-runner → documentation-expert → documentation-verifier → commit` flow, including the blocker path where the verifier prevents the commit when required docs are absent or placeholder.

## Completion Across a Batch — One Run Gives One Answer Per Condition

When one run of `templates/workflows-js/build-feature.js` carries several tickets, each
ticket's close verdict is a pure function of that ticket's **own** read-back record. The
demanded-step set comes only from that record per
[ADR-046](../adrs/ADR-046-completion-demanded-set-is-record-only.md), and per
[ADR-048](../adrs/ADR-048-order-independent-per-ticket-completion.md) no state the run
accumulates as it proceeds — no memo, cache, running tally, batch index, chunk position,
or shared sub-agent session — is an input to any ticket's verdict or to the close dispatch
performed for it. Two consequences follow rather than being separately implemented: two
tickets in the identical state always receive the identical answer regardless of the order
the run reached them, and a second run over the same records reproduces the first run's
answers ticket for ticket. This invariant holds today as a consequence of the record-only
derivation landed for ADR-046; `BO-400e-4` confirmed it by executing a real four-ticket
run rather than by reading the source, and no production behaviour changed to obtain it.

One value genuinely is shared across tickets within a run, and it is worth naming so a
future reader does not mistake it for a violation: `completedTicketOutcomes`. It is read
**only** by the `depends_on` eligibility gate — whether a dependent ticket is dispatched at
all — and is **never** read by the completion verdict itself (`concludeTicket` /
`completionVerdictFromRecord`). Eligibility and verdict are separate questions; only the
latter is under the no-shared-state rule.

"All the tickets in the run agreed" is **not** sufficient evidence on its own: a run that
refuses everything is trivially consistent, trivially repeatable, and trivially
order-independent. The invariant therefore requires a contrasting case in the same run —
at least one ticket whose record carries a passing sign-off for every phase it names must
be written finished, through the single-writer mechanism. Determinism obtained by uniform
refusal is inadmissible per
[ADR-048](../adrs/ADR-048-order-independent-per-ticket-completion.md) §7, which also
explains why that would convert a phantom-done into a phantom-blocked.

```mermaid
sequenceDiagram
    autonumber
    participant Run as One run of build-feature.js
    participant R1 as Ticket 01 record
    participant R2 as Ticket 03 record
    participant R3 as Ticket 20 record
    participant R4 as Control ticket record
    participant Writer as scripts/set_ticket_status.py

    Note over Run,R4: Tickets 01, 03 and 20 are in the identical state — same phases named<br/>needed, all signed off except pull-request, which none of the three carries.

    Run->>R1: read back this ticket's own record
    R1-->>Run: needed phases + sign-offs; no pull-request entry
    Run->>Run: verdict — refuse; record left as found; outstanding phase: pull-request

    Run->>R2: read back this ticket's own record
    R2-->>Run: needed phases + sign-offs; no pull-request entry
    Run->>Run: verdict — refuse; record left as found; outstanding phase: pull-request

    Run->>R3: read back this ticket's own record
    R3-->>Run: needed phases + sign-offs; no pull-request entry
    Run->>Run: verdict — refuse; record left as found; outstanding phase: pull-request

    Run->>R4: read back this ticket's own record
    R4-->>Run: every phase this ticket names is signed off
    Run->>Writer: close this ticket — unforced, own fresh dispatch
    Writer-->>R4: status done written

    Note over Run,Writer: Reach-order changes none of these four answers, and a second run<br/>over the same four records reproduces all four.
```

The contrast inside the single run is the whole point: three refusals that name the same
outstanding phase and leave three records untouched, alongside one separately-signed-off
control ticket written finished by the same run through the same single writer. Without the
control, the three matching refusals would prove only that the run is consistent; with it,
they are attributable to the missing sign-off. This is also why conformance is demonstrated
by a four-ticket run and never by four independent single-ticket runs — at one ticket per
run there is nothing to carry between tickets, so the property under test cannot fail.

A future change that reintroduces cross-ticket state into the verdict — a run-scoped cache
of a re-read record, a batch-level close dispatch, a sub-agent session reused across closes
— is breaking something deliberate, not performing a harmless refactor. Both drivers
(`build-feature.js` and `build-ticket.js`) are bound by this, in the same commit, even
though the single-ticket driver cannot exhibit the disagreement.
