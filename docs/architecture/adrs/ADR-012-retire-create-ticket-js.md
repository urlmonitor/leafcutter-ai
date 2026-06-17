---
title: "ADR-012: Retire create-ticket.js — /plan-feature + /build-ac as Canonical Ticket-Creation Path"
description: "Decision to retire the create-ticket.js workflow via a runtime guard and adopt /plan-feature + /build-ac as the canonical ticket-creation path."
type: "adr"
status: "accepted"
created: "2026-06-16"
last_updated: "2026-06-16"
deciders:
  - BrainCandy
components:
  - ticket_creation_pipeline
  - ac-store
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/adrs/ADR-007-contract-driven-acs.md
  - templates/workflows-js/create-ticket.js
---

# ADR-012: Retire create-ticket.js — /plan-feature + /build-ac as Canonical Ticket-Creation Path

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-06-16 |
| Deciders | BrainCandy |
| Author | llm-expert (EPIC-AcPipelineDeployGaps ticket 01) |
| Supersedes | — |
| Context ADRs | ADR-010 (source-of-truth inversion), ADR-006 (supervisor chain flattening) |

## Context

### The create-ticket.js pipeline

`templates/workflows-js/create-ticket.js` was introduced during
EPIC-FlattenSupervisorChain (ADR-006) to replace a depth-violating agent chain
with a flat sequential dispatch pattern. It implemented the following flow:

```
create-ticket.js (depth 0)
  ├── business-analyst   (depth 1) → returns JSON payload
  ├── user-prompt        (depth 0, conditional on open_questions)
  └── architect-review   (depth 1, conditional on requires_architect_review)
```

The workflow consumed four specific fields from the `business-analyst` return:

| Field | Purpose in create-ticket.js |
|---|---|
| `routing_decision` | Routes to epic path vs standard-ticket path |
| `open_questions` | Triggers user-prompt gate when non-empty |
| `requires_architect_review` | Conditions architect-review dispatch |
| `ticket_path` | The location of the ticket file written by BA |

### The v3 business-analyst contract

ADR-007 (Contract-Driven ACs) and ADR-007b (AC Store Schema) established the
AC YAML store as the structured requirements surface. In the v3 business-analyst
(introduced post-ADR-007), the agent operates exclusively at L2/L3 and produces
**AC YAML files** — not a JSON payload. It does not return any of the four fields
above; they are all undefined at runtime.

The consequence is a silent primary-deliverable failure:

- `routing_decision === undefined` → the routing gate is always falsy; the epic
  path is never taken; the standard-ticket path always runs.
- `open_questions === undefined` → the user-prompt gate never fires.
- `requires_architect_review === undefined` → JavaScript's `!== false` guard
  evaluates to `true` for `undefined`, so architect-review is dispatched on
  every run even for trivial tickets.
- `ticket_path === undefined` → no ticket file path is returned; no ticket file
  is ever produced.

Unit tests for create-ticket.js pass green because they assert only that the
create-epic error string is absent, never that a ticket file exists on disk.
This masked the failure completely.

### ADR-010: The source-of-truth inversion

ADR-010 (Accepted, 2026-06-05) formally inverted the source-of-truth:

> **The AC YAML store becomes the authoritative source of truth for the
> leafcutter-ai build backlog.** Tickets remain the unit of execution, but they
> are now *derived artefacts* generated from the AC store rather than primary
> hand-authored inputs.

ADR-010 named `/build-ac` (via `scan_ac_store.py` + `generate_ticket_from_ac.py`)
as the authoritative backlog-to-ticket path. It explicitly described the
`create-ticket` orchestrator and the `business-analyst` / IT PO pipeline as
unchanged "neutral" consequences — a signal that the manual pipeline coexists
during the transition but is not the forward direction.

After ADR-010, `create-ticket.js` represents a pattern that:

1. Bypasses the AC store's `depends_on` ordering, `work_status` tracking, and
   `implemented_by` back-write — all of which `generate_ticket_from_ac.py`
   provides automatically.
2. Requires the business-analyst to produce an intermediate JSON payload that
   the v3 BA was deliberately redesigned away from.
3. Duplicates the pipeline shape of `/plan-feature + /build-ac` without the
   store-integration benefits.

## Options Considered

### Option A — Rewrite create-ticket.js around the AC-store model

Rewrite the workflow to consume v3 business-analyst AC YAML output (or read the
AC store directly) and produce a valid ticket file.

**Rejected.** This effectively duplicates the `/plan-feature + /build-ac` pipeline
shape — the BA and IT PO authors AC YAML in the same store that `scan_ac_store.py`
and `generate_ticket_from_ac.py` already read from. Rewriting `create-ticket.js`
to do the same thing adds a parallel path with no incremental value. It would
also create a second implementation of the store-integration logic that could
drift from the canonical scripts. The maintenance burden grows for zero benefit
compared to directing users to `/plan-feature + /build-ac`.

### Option B — Re-point create-ticket.js at a dedicated ticket-drafting agent

Create a new ticket-drafting agent that accepts AC YAML and produces a ticket
file, and re-point `create-ticket.js` to dispatch it.

**Rejected.** The AC store already has `generate_ticket_from_ac.py` for exactly
this purpose. The script provides dependency ordering (`depends_on` resolution),
work-status tracking (`work_status: todo` guard), and bidirectional traceability
(`implemented_by` back-write). A new dedicated agent would re-solve a solved
problem and add an agent surface that bypasses the store's idempotency guard —
re-running ticket generation for the same AC would produce duplicates.

### Option C — Retire create-ticket.js entirely (chosen)

Remove `create-ticket.js` as a live dispatch path. Document the retirement with a
clear error message in the file body. Designate `/plan-feature + /build-ac` as
the canonical ticket-creation path.

**Accepted.** This is the only option that:

- Eliminates the silent-failure surface without introducing a parallel path.
- Consolidates on the ADR-010 pipeline, which already covers the full
  PO → BA → IT PO → ticket generation flow.
- Reduces pipeline surface area rather than expanding it.
- Is reversible: if `/plan-feature + /build-ac` proves insufficient, `create-ticket.js`
  can be rehabilitated by re-implementing the four consumed fields in a dedicated
  ticket-authoring agent and wiring it into the AC store.

The trade-off ruled out by Option A: patching a stale contract around a path
ADR-010 explicitly superseded creates ongoing maintenance burden and architectural
confusion. The trade-off ruled out by Option B: adding a new agent for ticket
drafting duplicates functionality already present in `generate_ticket_from_ac.py`.

## Decision

**`create-ticket.js` is retired as a live user-facing entry point.**

The retirement is implemented in two steps (per EPIC-AcPipelineDeployGaps ticket 01):

1. **llm-expert (this ADR)**: Add a retirement comment block to `create-ticket.js`
   header; add a runtime guard in `run()` that immediately returns `{status: "error",
   exit_code: 1}` with the canonical-path message. Retain the dead implementation
   below the guard for archaeological reference. Author this ADR.

2. **python-coder**: Remove or stub `create-ticket.js` per AC-6 of ticket 01.
   Verify that no active routing logic dispatches to it (AC-6-Edge). Update unit
   tests to assert the retirement contract (AC-7).

The canonical ticket-creation path is:

```
/plan-feature   ←  PO → BA → IT PO authoring pipeline
                    produces AC YAML in docs/acceptance-criteria/

/build-ac       ←  scan_ac_store.py selects the next ready leaf AC
                    generate_ticket_from_ac.py writes the ticket file
                    + implemented_by back-write to the source AC YAML
                    user runs /build-feature to drive the ticket
```

This path:

- Derives tickets from the AC store (ADR-010 source-of-truth model).
- Respects `depends_on` ordering computed by `scan_ac_store.py`.
- Writes `implemented_by` back-links automatically (`generate_ticket_from_ac.py`).
- Is idempotent: the generator guards against re-generating a ticket for an AC
  that already has an `implemented_by` entry.

## Consequences

### Positive

- **Eliminates a silent-failure surface.** The pre-retirement `create-ticket.js`
  never produced a ticket file when invoked with the v3 BA. This failure was
  invisible: the workflow returned `{status: "ok"}` with a `ticket_path: undefined`.
  After retirement, any invocation immediately returns `{status: "error", exit_code: 1}`
  with a message directing users to the canonical path.

- **Consolidates on the ADR-010 model.** The AC store becomes the single backlog
  surface; `generate_ticket_from_ac.py` becomes the single ticket-generation
  mechanism. Users no longer need to reason about which pipeline to use.

- **Reduces surface area.** One fewer workflow script to maintain and test.
  The routing, questioning, and architect-review logic in `create-ticket.js` is
  replaced by the AC store's field-driven routing (priority, depends_on).

### Negative

- **Users familiar with `/create-ticket` must migrate.** Users who were invoking
  `/create-ticket` (or `create-ticket.js`) as their primary ticket-creation
  mechanism must learn `/plan-feature + /build-ac`. Migration guidance is provided
  in `docs/how-to/` (the documentation-expert phase of ticket 01).

- **Hand-written tickets for novel or exploratory work lose a workflow entry.**
  `create-ticket.js` supported an ad-hoc narrative request → ticket path. Users
  who need a quick hand-authored ticket for novel work must either author the
  ticket directly (no workflow support) or go through `/plan-feature + /build-ac`
  (which authors AC YAML first). For genuinely exploratory work, the AC-first
  model adds upfront structure that may feel like overhead.

- **`create-ticket.js` is retained on disk (as dead code).** The file is not
  deleted in this ticket to provide an archaeological reference for the pre-v3
  contract. The python-coder phase (ticket 01, Option C tasks) decides whether
  to delete the file or stub it per AC-6.

### Neutral

- The `create-ticket` agent template (`templates/agents/create-ticket.md`) is
  not modified by this ADR. It dispatches `create-ticket.js` when available and
  falls back to prompting the user for the BA agent directly. After the
  python-coder phase stubs or removes `create-ticket.js`, the fallback prompt
  should also be updated to name the canonical path.

- The `/create-ticket` slash command surface is unaffected by this file-level
  change until the agent template itself is updated in the documentation-expert
  phase.

## Alternatives Summary

| Option | Outcome |
|---|---|
| A — Rewrite around AC store | Rejected: duplicates /plan-feature + /build-ac with no benefit |
| B — New ticket-drafting agent | Rejected: duplicates generate_ticket_from_ac.py |
| C — Retire entirely | **Accepted**: eliminates silent failure, consolidates on ADR-010 |

## References

- [ADR-010 — AC Store as Authoritative Backlog](ADR-010-ac-store-as-authoritative-backlog.md) — establishes the source-of-truth inversion; names `/build-ac` as the authoritative backlog-to-ticket path.
- [ADR-006 — Flatten the Supervisor Chain](ADR-006-flatten-supervisor-chain.md) — the ADR under which `create-ticket.js` was originally written; provides the depth-1 context for the workflow script pattern.
- [ADR-007 — Contract-Driven Acceptance Criteria](ADR-007-contract-driven-acs.md) — establishes the per-agent AC format that the v3 business-analyst produces.
- [templates/workflows-js/create-ticket.js](../../../templates/workflows-js/create-ticket.js) — the retired file; contains the runtime retirement guard added by this ADR.
- EPIC-AcPipelineDeployGaps ticket 01 — the commissioning ticket for this retirement; the architect-review comment records the adjudication rationale.
