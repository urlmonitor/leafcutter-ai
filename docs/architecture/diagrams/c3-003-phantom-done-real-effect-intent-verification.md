---
title: "Phantom-Done Prevention — Proving a Durable Change by Real Effect and Intent"
description: "L3 sequence diagram of the BP-1100f verification flow: how a durable change is proven by its real effect and stated intent (not by dispatch topology), showing where each of the five gates sits relative to dispatch and to the done state — the pre-dispatch intent-vs-surface consistency check (BP-1100f-3), the instruction-carrying dispatch review (BP-1100f-1), the harness-level instruction-less-dispatch contract violation (BP-1100f-4), the real-artifact test-evidence requirement (BP-1100f-2), and the automatic observable-side-effect smoke check (BP-1100f-5)."
type: architecture
diagram_type: sequence
status: active
flight_level: L3-Component
created: 2026-07-21
last_updated: 2026-07-21
parent: docs/architecture/components/phantom-done-prevention.md
source_ticket: tickets/00_inbox/TICKET-20260721-BP-1100f-6.md
components:
  - build_pipeline
  - build_orchestration
related_docs:
  - docs/architecture/components/phantom-done-prevention.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/agent_delivery_workflows.md
  - docs/architecture/diagrams/c2-006-feature-to-merged-pr.md
related_code:
  - templates/agents/it-po.md
  - templates/agents/pr-reviewer.md
  - templates/agents/test-writer.md
  - unit_tests/_workflow_engine_harness.py
  - config/agent_registry.json
  - scripts/ac_store/generate_ticket_from_ac.py
  - templates/workflows-js/build-ticket.js
related_adrs:
  - ADR-001
  - ADR-020
tags:
  - phantom-done
  - real-effect
  - real-intent
  - dispatch-topology
  - verification-gate
---

# Phantom-Done Prevention — Proving a Durable Change by Real Effect and Intent

This diagram documents the end-to-end **BP-1100f** verification flow: how the build
pipeline proves that a durable change actually happened by its **real effect** and its
**stated intent**, rather than by **dispatch topology** — the presence, labels, or counts
of dispatched helpers that a test mock controls. It shows, for each of the five gates,
the precise point at which it gates the work item **relative to dispatch and to the done
state**.

> **Why this exists — the BO-2300 failure mode.** "Interactive Pause/Resume" was signed
> off as done twice while its real behaviour was absent, because its tests keyed off
> dispatch *topology* (labels/counts the harness mock controls) rather than the
> instruction *payload* and the on-disk *effect*. Each gate below moves proof away from
> "a step ran" and toward "the real effect exists / the stated intent is coherent". Any
> project that installs leafcutter and runs `build.py` gets these gates the same way
> (portable per ADR-001).

The five gates and where they sit on the timeline:

| Gate | AC | Position relative to dispatch / done | Proves by |
|------|----|--------------------------------------|-----------|
| 1 — Intent-vs-surface consistency (IT-PO) | BP-1100f-3 | **Before** any implementer is dispatched | Intent (assigned agent + checking framework matches the declared surface) |
| 2 — Instruction-carrying dispatch review (pr-reviewer) | BP-1100f-1 | **At** dispatch review, before the dispatch is accepted | Intent (the dispatch carries a real, actionable instruction) |
| 3 — Instruction-less-dispatch harness violation | BP-1100f-4 | **At test time**, mechanically | Intent (a content-free dispatch fails the test even if the double returns success) |
| 4 — Real-artifact test-evidence requirement (pr-reviewer / test-writer) | BP-1100f-2 | **At coverage-sufficiency**, after implementation | Effect (a real-effect round-trip: produce the artifact, read it back) |
| 5 — Automatic observable-side-effect smoke check | BP-1100f-5 | **In the verification phase**, gating the done state | Effect (the observable side-effect is exercised before done) |

---

```mermaid
sequenceDiagram
    autonumber
    participant WI as Work item<br/>(stated intent + declared surface)
    participant ITPO as IT-PO<br/>(pre-dispatch consistency lens)
    participant Rev as pr-reviewer<br/>(dispatch + evidence lenses)
    participant Impl as Implementer<br/>(dispatched helper)
    participant Harness as Workflow test harness<br/>(agent() interceptor)
    participant Verify as Verification phase<br/>(user-surface-smoker)
    participant Done as Done state

    Note over WI,Done: Work is proven done by REAL EFFECT / STATED INTENT — never by dispatch topology (labels/counts a mock controls). BO-2300 failure mode.

    rect rgb(232, 244, 253)
    Note over WI,ITPO: GATE 1 — BP-1100f-3 · PRE-DISPATCH (before any implementer is dispatched)
    WI->>ITPO: intent (assigned agent + checking framework) vs declared surface (files_touched)
    alt intent contradicts surface — e.g. python-coder + pytest aimed at a .js surface
        ITPO-->>WI: FLAG — mismatch named; blocked before work begins
    else intent matches surface
        ITPO-->>Rev: consistent — proceed to dispatch review
    end
    end

    rect rgb(232, 244, 253)
    Note over Rev,Impl: GATE 2 — BP-1100f-1 · AT DISPATCH REVIEW (before the dispatch is accepted)
    Rev->>Rev: inspect proposed agent() dispatch first argument
    alt first arg is a bare object / empty value — no instruction text
        Rev-->>WI: FLAG — dispatch carries no actionable instruction; not accepted
    else first arg is a non-empty instruction string
        Rev->>Impl: dispatch accepted — instruction carried
    end
    end

    Impl->>Impl: produce the durable change (artifact written to disk)

    rect rgb(255, 243, 224)
    Note over Impl,Harness: GATE 3 — BP-1100f-4 · HARNESS LEVEL (at test time; mechanical)
    Impl->>Harness: workflow test exercises the dispatch
    Harness->>Harness: intercept agent() first argument
    alt instruction-less first arg (object/empty) — even if the double is stubbed to return success
        Harness-->>WI: CONTRACT VIOLATION — names the instruction-less dispatch; test fails
    else non-empty instruction string
        Harness-->>WI: no violation — test proceeds
    end
    end

    rect rgb(232, 245, 233)
    Note over WI,Rev: GATE 4 — BP-1100f-2 · TEST-EVIDENCE SUFFICIENCY (coverage check, after implementation)
    Rev->>Rev: classify the declared side-effect's test evidence
    alt evidence is DISPATCH TOPOLOGY only — presence / labels / counts a mock controls
        Rev-->>WI: side-effect reported UNCOVERED — a step ran, but the effect is unproven
    else evidence includes a REAL-EFFECT round-trip — produce the artifact, then read it back
        Rev-->>WI: covered — the real effect is proven
    end
    end

    rect rgb(232, 245, 233)
    Note over WI,Done: GATE 5 — BP-1100f-5 · VERIFICATION PHASE (automatic; gates the done state)
    WI->>Verify: routed by DECLARED durable side-effect (data-driven, not an opt-in flag)
    Verify->>Verify: run observable-side-effect smoke check; produce a smoke result
    Note over Verify: BP-1100f-5 implementation is pending a design decision;<br/>this depicts the INTENDED role the AC specifies.
    alt smoke unrun or silently skipped
        Verify-->>WI: blocked — cannot reach done with the smoke check unrun
    else smoke result observed
        Verify->>Done: real effect observed — work item may reach done
    end
    end

    Note over WI,Done: Every gate proves the change by its real effect / stated intent, at a defined point relative to dispatch and to the done state — replacing proof-by-dispatch-topology.
```

Parent: [Phantom-Done Prevention — Real-Effect / Real-Intent Verification (Container Overview)](../components/phantom-done-prevention.md)

See also: [Build Orchestration — Epic & Ticket Dispatch Sequencing](../components/build-orchestration.md) — the component that owns the drive/verification-phase routing these gates plug into.

---

## Gate-by-gate walk-through

Reading the timeline left-to-right, each gate is anchored to a fixed point relative to
**dispatch** and to the **done state**:

1. **Intent-vs-surface consistency — BP-1100f-3 (pre-dispatch).** Before the first
   implementer is dispatched, the IT-PO consistency lens compares the work item's stated
   intent (assigned implementer + its checking test framework) against its declared
   surface (`files_touched` extensions). A technology *contradiction* — e.g. a
   `python-coder` checked by `pytest` aimed at a JavaScript surface — is named and blocked
   *before* work begins (RCA Failure #1). A matching implementer/surface passes unflagged.
   This proves **intent**, not topology.

2. **Instruction-carrying dispatch review — BP-1100f-1 (at dispatch review).** The
   pr-reviewer inspects the *proposed* `agent()` dispatch: if its first argument is a bare
   object or an empty value carrying no instruction text, the step is flagged and **not
   accepted**, with the finding naming the dispatch as instruction-less. A first argument
   that is a non-empty instruction string describing the change passes unflagged (RCA
   Failure #2). The gate sits *before the dispatch is accepted*.

3. **Instruction-less-dispatch harness violation — BP-1100f-4 (at test time).** The
   workflow test harness (`unit_tests/_workflow_engine_harness.py`) intercepts the
   dispatch mechanically. An instruction-less first argument raises a `contract_violation`
   (`kind: instruction_less_dispatch`) that names the dispatch and fails the test — and it
   fires *even when the dispatch double is stubbed to return a success value*, so a
   return-value stub cannot suppress it. This is the mechanical counterpart to Gate 2 and
   maintains spec parity with the same "instruction-less first argument" definition.

4. **Real-artifact test-evidence requirement — BP-1100f-2 (coverage-sufficiency).** After
   implementation, the pr-reviewer evidence lens (and the test-writer authoring mandate)
   classify the evidence for a declared durable side-effect. Evidence that is *dispatch
   topology only* — the presence, labels, or counts of dispatched helpers a mock controls
   — reports the side-effect as **uncovered**: it proves a step ran, not that the effect
   occurred. Coverage is satisfied only once the evidence includes at least one
   **real-effect round-trip** test that produces the artifact and reads it back. This is
   the explicit "topology vs effect" distinction at the heart of the BO-2300 RCA.

5. **Automatic observable-side-effect smoke check — BP-1100f-5 (verification phase, gates
   done).** In the work item's verification phase, the observable-side-effect smoke check
   runs **automatically** — selected by the work item's *declared durable side-effect*
   (data-driven), not by an opt-in flag — and produces a smoke result. The work item
   **cannot reach a done state** with the smoke check left unrun or silently skipped; an
   item declaring no durable side-effect (e.g. a docs-only change) is not force-routed.
   *Note:* the exact declared field and its enforcement are pending a design decision
   (broaden `user_facing_surface` vs. add a durable-side-effect axis); this diagram
   depicts the **intended** role the AC specifies, not a shipped selector.

**Proof by real effect/intent vs proof by dispatch topology.** The blue gates (1–3) prove
**intent** — the work is coherent and carries a real instruction *before and around*
dispatch. The green gates (4–5) prove **effect** — the durable artifact actually exists
and is exercised *after* implementation and *before* done. None of the gates accept
"a step ran" (dispatch topology) as proof on its own. That substitution is exactly the
phantom-done failure this flow prevents.

## Cross-References

- [Phantom-Done Prevention — Real-Effect / Real-Intent Verification (Container Overview)](../components/phantom-done-prevention.md) — the L2 container that groups these gates (parent).
- [Feature to Merged PR — End-to-End Sequence Diagram](c2-006-feature-to-merged-pr.md) — the L1 pipeline these gates annotate.
- [Build Orchestration — Epic & Ticket Dispatch Sequencing](../components/build-orchestration.md) — owns the drive/verification-phase routing (BP-1100f-5).
- [Agent Code Delivery Workflows](../agent_delivery_workflows.md) — supervisor dispatch topology and blocker adjudication, the dispatch surface these gates review.
- [ADR-001 — Self-Hosting Boundary](../adrs/ADR-001-self-hosting-boundary.md) — why each gate is packaged (portable to any consumer that runs build.py), not tied to the leafcutter repo's own root CLAUDE.md.
- [ADR-020 — Live Surface Tester](../adrs/ADR-020-live-surface-tester.md) — the observable-side-effect smoke surface Gate 5 routes to.
