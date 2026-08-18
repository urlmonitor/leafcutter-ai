---
title: "Phantom-Done Prevention — Real-Effect / Real-Intent Verification (Container Overview)"
description: "Container-level overview of the BP-1100f phantom-done-prevention gates: five checks that prove a durable change by its real effect and stated intent (not by dispatch topology), each anchored to a fixed point relative to dispatch and to the done state. Groups the L3 sequence diagram that documents the end-to-end verification flow."
type: architecture
status: active
flight_level: L2-Container
created: 2026-07-21
last_updated: 2026-08-18
source_ticket: tickets/00_inbox/TICKET-20260721-BP-1100f-6.md
components:
  - build_pipeline
  - build_orchestration
children:
  - docs/architecture/diagrams/c3-003-phantom-done-real-effect-intent-verification.md
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/agent_delivery_workflows.md
  - docs/architecture/diagrams/c2-006-feature-to-merged-pr.md
  - docs/architecture/diagrams/c3-003-phantom-done-real-effect-intent-verification.md
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

# Phantom-Done Prevention — Real-Effect / Real-Intent Verification

The **Phantom-Done Prevention** container groups the BP-1100f gates that defend against
the *proof-by-dispatch-topology* failure mode: a feature is signed off as done because a
step **ran**, rather than because its real effect **exists** and its stated intent is
**coherent**. This is the BO-2300 failure mode — "Interactive Pause/Resume" was
phantom-built twice because its tests keyed off dispatch topology (the presence, labels,
or counts of dispatched helpers that a test mock controls) rather than the instruction
payload and the on-disk effect.

Every gate here is packaged and portable per [ADR-001](adrs/ADR-001-self-hosting-boundary.md):
any project that installs leafcutter and runs `build.py` gets the same behaviour — the
gates do not depend on the leafcutter repo's own root `CLAUDE.md`.

This container is documented by one L3 child diagram at the component level:

- [Phantom-Done Prevention — Proving a Durable Change by Real Effect and Intent](../diagrams/c3-003-phantom-done-real-effect-intent-verification.md) — the end-to-end sequence showing where each of the five gates sits relative to dispatch and to the done state.

## The five gates

| Gate | AC | Surface | Position | Proves by |
|------|----|---------|----------|-----------|
| Intent-vs-surface consistency | BP-1100f-3 | IT-PO pre-dispatch consistency lens (`templates/agents/it-po.md`) | Before any implementer is dispatched | Intent — assigned agent + checking framework must match the declared surface |
| Instruction-carrying dispatch review | BP-1100f-1 | pr-reviewer dispatch lens (`templates/agents/pr-reviewer.md`) | At dispatch review, before the dispatch is accepted | Intent — the dispatch carries a real, actionable instruction string |
| Instruction-less-dispatch harness violation | BP-1100f-4 | Workflow test harness (`unit_tests/_workflow_engine_harness.py`) | At test time, mechanically | Intent — a content-free dispatch fails the test even if the double returns success |
| Real-artifact test-evidence requirement | BP-1100f-2 | pr-reviewer evidence lens + test-writer mandate (`templates/agents/pr-reviewer.md`, `templates/agents/test-writer.md`) | At coverage-sufficiency, after implementation | Effect — a real-effect round-trip: produce the artifact, read it back |
| Automatic observable-side-effect smoke check | BP-1100f-5 | Registry routing + generator + drive (`config/agent_registry.json`, `scripts/ac_store/generate_ticket_from_ac.py`, `templates/workflows-js/build-ticket.js`) | In the verification phase, gating the done state | Effect — the observable side-effect is exercised before done |

> **BP-1100f-5 status.** The exact declared field for the automatic side-effect routing
> (broaden `user_facing_surface` vs. add a durable-side-effect axis) is pending a design
> decision; the child diagram depicts its **intended** role as specified by the AC, not a
> shipped selector.

## Cross-References

- [AC-Driven Development — Coverage Resolution](ac-driven-dev.md#coverage-resolution--ac_coverage_resolver) — a sibling instance of this failure mode outside the five BP-1100f gates above: the `ac-fulfillment-gate` phase gate's coverage-resolution step signed off `ok` having verified zero ACs, because its "every AC in the working list passed or skipped" rule was vacuously true over an empty working list (`ACD-1900b-5-i`). Fixed by making the `ok` verdict structurally require at least one resolved AC.
- [Build Orchestration — Epic & Ticket Dispatch Sequencing](build-orchestration.md) — owns the drive/verification-phase routing the gates plug into.
- [Agent Code Delivery Workflows](../agent_delivery_workflows.md) — the supervisor dispatch topology and blocker adjudication these gates review.
- [Feature to Merged PR — End-to-End Sequence Diagram](../diagrams/c2-006-feature-to-merged-pr.md) — the end-to-end pipeline the gates annotate.
- [ADR-001 — Self-Hosting Boundary](adrs/ADR-001-self-hosting-boundary.md) — why each gate is packaged and portable.
- [ADR-020 — Live Surface Tester](adrs/ADR-020-live-surface-tester.md) — the observable-side-effect smoke surface Gate 5 routes to.
