---
title: "ADR-019: build-feature.js Inlines the Phase-Dispatch Loop"
description: "Records the decision to inline the driveTicketPhases loop from build-ticket.js directly into build-feature.js, replacing the prior pattern of dispatching a ticket-supervisor agent per ticket. The prior pattern silently placed phase agents at depth 2 — beyond Claude Code's hard depth-1 Agent-tool nesting limit — so no phase templates ever applied. The workflow() alternative is also prohibited by the E2 leaf-invariant. Inlining the loop is the only configuration that satisfies both constraints."
type: "adr"
status: "accepted"
created: "2026-07-09"
last_updated: "2026-07-09"
deciders:
  - leafcutter-engineering-team
components:
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/agent_delivery_workflows.md
related_code:
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
---

# ADR-019: build-feature.js Inlines the Phase-Dispatch Loop

## Status

Accepted (2026-07-09)

## Context

### The prior dispatch topology

`build-feature.js` previously drove epic-batch and single-ticket flows by:

1. Reading `Master_Plan.md` and all sub-tickets.
2. Building a dependency graph (`depends_on` + `files_touched` disjointness).
3. For each ticket in the next ready batch, dispatching `ticket-supervisor` via
   `agent()` — placing `ticket-supervisor` at **depth 1**.

From depth 1, `ticket-supervisor` attempted to spawn phase agents
(`python-coder`, `test-writer`, `adr-author`, etc.) via its own `agent()` calls.
Those calls would be at **depth 2** — beyond the Claude Code hard limit.

### The depth-1 limit

Claude Code's Agent tool imposes a hard cap: an agent running at depth 1 (invoked
via the Agent tool) cannot itself invoke the Agent tool. Any call beyond depth 1 is
silently dropped — no error is raised, the tool call simply does not execute. This
constraint is documented and diagnosed in ADR-006-flatten-supervisor-chain.md.

ADR-006 established that `ticket-supervisor` must run at depth 0. When
`build-feature.js` was wired to dispatch `ticket-supervisor` as an `agent()` call
per ticket, it placed `ticket-supervisor` back at depth 1, recreating the original
silent-failure mode.

The consequence: all phase agents were never spawned. Each ticket appeared to
progress (the per-ticket loop iterated), but no implementation work occurred on
disk, no tests ran, and no TDD red/green cycle was enforced. The ADR-006 intent was
declared done, but the phase-template application was silently absent from every
`/build-feature` run.

### The E2 leaf-invariant: no workflow() nesting

The Claude Code Workflow runtime enforces the **E2 leaf-invariant**: a workflow
script cannot invoke another workflow script via the `workflow()` tool. Any
`workflow()` call inside a running workflow throws at runtime.

This means `workflow('build-ticket')` cannot be called from within
`build-feature.js`. `build-ticket.js` contains the canonical `driveTicketPhases`
function, but it is unreachable via the `workflow()` mechanism from a running
`build-feature.js` context.

### The orphaned build-ticket.js

Since PR #198, `build-ticket.js` was unreachable from `build-feature.js` by both
mechanisms:

- `agent('ticket-supervisor')` → `ticket-supervisor` at depth 1 → phase agents at
  depth 2 → silently dropped.
- `workflow('build-ticket')` → E2 leaf-invariant → throws at runtime.

`build-ticket.js` was effectively orphaned as dead code in the `/build-feature`
dispatch path, while remaining the correct entry point when invoked standalone.

## Options Considered

### Option A — Keep dispatching ticket-supervisor via agent()

Leave `build-feature.js` dispatching `ticket-supervisor` via `agent()` per ticket.
Accept that phase agents are silently dropped.

**Rejected.** This is the broken status quo. Phase templates never apply. TDD
separation never fires. `/build-feature` produces no implementation output.

### Option B — Call workflow('build-ticket') from build-feature.js

Delegate the per-ticket phase loop to `build-ticket.js` via
`workflow('build-ticket')`.

**Rejected.** The E2 leaf-invariant prohibits a `workflow()` call from inside a
running workflow. This call throws at runtime. There is no version of the Workflow
runtime that permits it.

### Option C — Inline driveTicketPhases from build-ticket.js (chosen)

Copy the `driveTicketPhases` loop from `build-ticket.js` directly into
`build-feature.js`. Each needed phase is dispatched as its own
`agent(agentType: phaseName)` call from the `build-feature.js` executing context
(depth 0). Phase agents land at depth 1 — within the hard limit.

`build-ticket.js` is retained as the **canonical twin** with a TWIN comment
referencing `build-feature.js`. Both scripts carry the same `driveTicketPhases`
logic. Any change to the loop must be applied to both files.

## Decision

`build-feature.js` **inlines the `driveTicketPhases` loop** from `build-ticket.js`,
dispatching each phase as a depth-1 `agent(agentType: phaseName)` call. This applies
on both the epic-batch path (iterating over a `depends_on`-ordered ticket batch) and
the single-ticket path.

Concretely:

1. **`build-feature.js` is the depth-0 executing context.** It runs the batching
   logic (dependency graph, disjoint-files check, topological ordering) and the
   per-ticket phase-dispatch loop inline. It never calls `agent('ticket-supervisor')`
   for phase execution.

2. **Each phase agent runs at depth 1.** `agent('python-coder')`,
   `agent('test-writer')`, `agent('adr-author')`, etc. are dispatched directly from
   `build-feature.js` at depth 1. This is the only configuration that satisfies the
   Claude Code depth-1 constraint.

3. **`workflow('build-ticket')` is never called from `build-feature.js`.** The E2
   leaf-invariant prohibits nesting workflow scripts. `build-ticket.js` is the
   canonical single-ticket entry point when invoked directly; it is NOT reachable
   from `build-feature.js` via `workflow()`.

4. **`build-ticket.js` is retained as the canonical twin.** Both files carry the
   `driveTicketPhases` loop with TWIN comments that mark the intentional duplication
   and require that changes apply to both. `build-ticket.js` remains the reference
   implementation and the authoritative entry point for standalone single-ticket
   invocations.

5. **Batching, depends_on ordering, worktree guard, and failure adjudication are
   preserved.** These responsibilities remain in `build-feature.js` and are
   unchanged by this decision.

### Depth diagram after this change

```
/build-feature (JS workflow, depth 0 — batching + driveTicketPhases inline)
  ├── agent('architect-review')     (depth 1)
  ├── agent('python-coder')         (depth 1)
  ├── agent('sql-coder')            (depth 1)
  ├── agent('frontend-coder')       (depth 1)
  ├── agent('test-writer')          (depth 1)
  ├── agent('test-runner')          (depth 1)
  ├── agent('documentation-expert') (depth 1)
  ├── agent('pr-reviewer')          (depth 1)
  ├── agent('commit')               (depth 1)
  └── agent('pull-request')         (depth 1)
  (loop repeats for each ticket in batch — no Agent-tool call for the loop itself)
```

No `ticket-supervisor` agent is dispatched. No `workflow('build-ticket')` call is
made.

## Consequences

### Positive

- **Phase templates now apply on /build-feature.** Each `agent(agentType: phaseName)`
  call runs the named agent's full template, including skill loads and sign-off
  protocol.
- **TDD separation is restored.** `test-writer` is dispatched at priority 5 (before
  `python-coder`), enforcing the red-before-green phase invariant that was silently
  absent while `ticket-supervisor` was dispatched at depth 1.
- **ADR-006 intent is fully realised.** ADR-006 established that phase agents must
  run at depth 1. This change wires `build-feature.js` so that is actually true,
  completing ADR-006's intent.
- **E2 leaf-invariant honoured.** No `workflow()` nesting exists anywhere in the
  dispatch path.
- **build-ticket.js is no longer dead code.** It is reinstated as the correct
  standalone single-ticket entry point; its `driveTicketPhases` function is the
  reference source for the loop now inlined in `build-feature.js`.

### Negative

- **`driveTicketPhases` is duplicated across two files.** `build-feature.js` and
  `build-ticket.js` carry identical loop logic. Any change to the phase ordering,
  failure adjudication ladder, or phase-skip rules must be applied to both files.
  TWIN comments mark the coupling; there is no mechanical enforcement to prevent
  drift between the two copies.
- **`ticket-supervisor` is no longer dispatched by `/build-feature` for phase
  execution.** The full phase-dispatch loop is now inline code in `build-feature.js`
  rather than a named, separately-invocable agent. Users invoking `ticket-supervisor`
  directly (standalone) are unaffected; only the `/build-feature` path changes.

### Neutral

- `build-ticket.js` is no longer orphaned. It remains the correct single-ticket
  entry point and the canonical TWIN. Its `driveTicketPhases` function is the
  reference implementation.
- The `building-epics` SKILL.md §1.1 pseudocode is unchanged. It remains the
  authoritative description of the batching algorithm implemented inline in
  `build-feature.js`.

## Alternatives Rejected

| Alternative | Why rejected |
|---|---|
| Dispatch `ticket-supervisor` via `agent()` | Silently places phase agents at depth 2; they are never spawned |
| Call `workflow('build-ticket')` | E2 leaf-invariant: throws at runtime when called from inside a running workflow |

## References

- `templates/workflows-js/build-feature.js` — the script this decision modifies;
  now carries the inlined `driveTicketPhases` loop.
- `templates/workflows-js/build-ticket.js` — the canonical twin; source of
  `driveTicketPhases`; carries a TWIN comment referencing `build-feature.js`.
- `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` — the earlier ADR
  whose intent this decision completes; established the depth-1 phase-agent rule.
- `docs/architecture/agent_delivery_workflows.md` §4 — the dispatch topology diagram
  updated to reflect this decision.
- Ticket `06_buildfeature_flatten_wiring.md` (EPIC-PromptAssemblyHardening), AC
  L1 BO-2000f — the implementation ticket that produced this change.
