---
title: "ADR-006: Flatten the Supervisor Chain — ticket-supervisor at Depth 0"
type: "adr"
status: "accepted"
created: "2026-05-29"
last_updated: "2026-05-29"
components:
  - build_pipeline
---

# ADR-006: Flatten the Supervisor Chain — ticket-supervisor at Depth 0

## Status

Accepted (2026-05-29)

## Context

The leafcutter-ai agentic build pipeline originally operated with a three-tier
dispatch chain:

```
/build-feature (user-facing entry)
  └── epic-supervisor   (depth 0)
        └── ticket-supervisor  (depth 1)
              └── phase agents  (depth 2)
                    e.g. adr-author, python-coder, pr-reviewer, commit
```

This architecture was designed under the assumption that Claude Code's Agent tool
supports arbitrary nesting depth. In practice, Claude Code imposes a **hard
depth-1 limit** on Agent-tool nesting: a sub-agent invoked at depth 1 cannot
itself invoke the Agent tool. Any call beyond depth 1 is silently blocked — no
error is raised, the tool call simply does not fire.

The consequence for the three-tier chain: when `ticket-supervisor` (depth 1)
attempted to spawn `adr-author`, `python-coder`, or any other phase agent, the
Agent tool call was silently dropped. The phase agent never ran. The ticket
appeared to progress (the supervisor loop iterated) while no actual work
occurred on disk.

This failure mode was first observed and confirmed during the initial attempt to
build EPIC-FlattenSupervisorChain. PR #22 was opened against the main branch
with a proposed solution (adding a pass-through shim at depth 1) and subsequently
**reverted** after the shim was found to reproduce the same nesting violation one
level deeper.

### The depth-1 limit in detail

Claude Code's Agent tool documentation states:

> Subagents called via the Agent tool are capped at one level of nesting. An
> agent running at depth 1 (i.e., itself invoked via the Agent tool) cannot
> invoke the Agent tool further.

This is a hard platform constraint, not a configurable threshold. There is no
workaround within the Agent tool's invocation model.

### Why epic-supervisor compounded the problem

The original role of `epic-supervisor` was:

1. Read the `Master_Plan.md` and all ticket files in the epic folder.
2. Build a dependency graph and compute a parallel-safe batch of ready tickets.
3. Spawn one `ticket-supervisor` per ticket in the batch (via the Agent tool).

Step 3 placed `ticket-supervisor` at depth 1. From that position,
`ticket-supervisor` could not spawn its phase agents. The epic-supervisor added
a tier of management that, under the depth-1 constraint, made phase agents
unreachable.

## Options Considered

### Option A — Keep epic-supervisor as a thin pass-through shim

Reduce `epic-supervisor` to a minimal wrapper that re-invokes
`ticket-supervisor` without itself using the Agent tool (using a subprocess or
direct Python call instead). `ticket-supervisor` would then sit at depth 0 and
retain the ability to spawn phase agents at depth 1.

**Rejected.** A subprocess-based shim breaks the Claude Code execution model:
the supervisor loses the ability to read tool output, stream reasoning, or
participate in the session context. The shim cannot participate in the
commit-phase serialization lock protocol either, since it runs out-of-process.
The shim pattern also reintroduces a coordination tier at zero benefit to the
user.

### Option B — Remove epic-supervisor entirely

Delete `epic-supervisor` and its template, and move all batching logic into
`/build-feature` inline.

**Rejected.** Outright deletion is not safe during a live migration. Existing
installations of leafcutter-ai reference `epic-supervisor` in their
`agent_registry.json`, in saved workflows, and in documentation. A hard deletion
breaks those references without a deprecation window. Additionally, the batching
algorithm in `epic-supervisor` is complex enough that it should be retained
in readable form during the transition period so that the logic can be ported
incrementally into `/build-feature` without loss of correctness.

### Option C — Inline batching in /build-feature; dispatch ticket-supervisor directly (chosen)

Move the epic-level batching loop (dependency-graph construction, parallel-safe
batch computation) into `/build-feature` inline. `/build-feature` dispatches
`ticket-supervisor` directly, placing `ticket-supervisor` at depth 1. Phase
agents continue to be spawned by `ticket-supervisor` — but now they are at
depth 2 relative to `/build-feature`.

Wait — that still hits the depth-1 limit for ticket-supervisor's Agent calls.

The correct framing of Option C: **`/build-feature` does NOT use the Agent tool
to dispatch `ticket-supervisor`**. Instead, `/build-feature` is the top-level
user-facing slash command; it runs inline (no Agent nesting). It calls
`ticket-supervisor` by invoking the agent definition directly as the executing
context (i.e., the slash command's own prompt IS the ticket-supervisor). Phase
agents are then spawned via the Agent tool from depth 0, placing them at depth 1
— within the hard limit.

Concretely:
- `/build-feature` (slash command, depth 0) performs the batching logic inline
  and drives one ticket at a time through `ticket-supervisor`'s algorithm.
- `ticket-supervisor` runs at depth 0 (it IS the executing context, not a
  spawned sub-agent).
- Phase agents (`adr-author`, `python-coder`, `pr-reviewer`, `commit`, etc.)
  are spawned via the Agent tool at depth 1.

This is the only configuration that satisfies the depth-1 constraint without a
subprocess shim.

## Decision

The supervisor chain is **flattened** as follows:

1. **`ticket-supervisor` runs at depth 0.** It is dispatched directly by
   `/build-feature` (or by the user invoking it explicitly for a single-ticket
   workflow). It is never spawned via the Agent tool by another agent.

2. **Phase agents run at depth 1.** `ticket-supervisor` spawns each phase agent
   (`adr-author`, `architect-review`, `python-coder`, `sql-coder`,
   `frontend-coder`, `test-runner`, `pr-reviewer`, `commit`, `pull-request`,
   etc.) via the Agent tool. These calls are the only Agent-tool dispatches in
   the pipeline.

3. **`epic-supervisor` is deprecated, not deleted.** The agent template is
   retained in the repository for the duration of the deprecation window
   (EPIC-FlattenSupervisorChain). It is marked `deprecated: true` in
   `agent_registry.json`. Existing workflows that reference it continue to load
   but trigger a deprecation warning at the start of every run.

4. **Epic-level batching moves inline to `/build-feature`.** The dependency-graph
   construction, parallel-safe batch computation, and per-ticket dispatch logic
   from `epic-supervisor` §1.1 is inlined into the `/build-feature` slash command.
   The algorithm is identical; only the execution context changes.

### Depth diagram after flattening

```
/build-feature (slash command, depth 0 — batching inline)
  ├── ticket-supervisor  (depth 0 — executing context)
  │     ├── adr-author          (depth 1, Agent tool)
  │     ├── architect-review    (depth 1, Agent tool)
  │     ├── python-coder        (depth 1, Agent tool)
  │     ├── test-runner         (depth 1, Agent tool)
  │     ├── pr-reviewer         (depth 1, Agent tool)
  │     ├── commit              (depth 1, Agent tool)
  │     └── pull-request        (depth 1, Agent tool)
  └── (next ticket via inline loop — no Agent tool)
```

All Agent-tool dispatches occur at exactly one depth hop from the executing
context, satisfying the Claude Code depth-1 constraint.

## Consequences

### Positive

- **Phase agents are reliably reachable.** The depth-1 constraint is honoured
  by construction; no silent drops occur.
- **Single-ticket path is unchanged.** Users who invoke `ticket-supervisor`
  directly (e.g. via `/build-feature` for a single ticket) see no change in
  behaviour. The phase-agent dispatch loop is identical.
- **No subprocess shim required.** All coordination remains within the Claude
  Code session context, preserving tool-output streaming, session-level memory,
  and the commit-phase serialization lock protocol.
- **Deprecation window for epic-supervisor.** Existing installations that have
  customised `epic-supervisor` prompts retain a working reference during the
  migration period.

### Negative

- **Epic-level batching is now inline in /build-feature.** The algorithm
  (dependency-graph construction, `files_touched` disjointness check, topological
  ordering) previously lived in a named, reviewable agent template. As inline
  logic it must be maintained directly in the slash command definition, which is
  less discoverable. Mitigation: `building-epics` SKILL.md §1 remains the
  canonical algorithm reference; `/build-feature` cites it explicitly.
- **`epic-supervisor` carries deprecation overhead.** The template must be
  updated (deprecation flag, warning comment) and eventually removed. This is
  a small but real maintenance cost for the transition period.
- **Parallel-ticket dispatch at the epic level is now serialised.** The original
  `epic-supervisor` §1 dispatched a batch of parallel-safe tickets concurrently
  via multiple simultaneous Agent tool calls. After flattening, `/build-feature`
  runs `ticket-supervisor` sequentially (one ticket at a time). Tickets that were
  previously co-dispatched now run in series. For the current phase-1 MVP scope
  this is acceptable — parallelism can be reintroduced later via a session-level
  concurrent-dispatch mechanism if needed.

### Neutral

- The `building-epics` SKILL.md §1.1 pseudocode is retained as documentation.
  The `epic-supervisor` agent continues to reference it during the deprecation
  window. After `epic-supervisor` is removed, §1.1 serves as the authoritative
  description of the algorithm now implemented inline in `/build-feature`.
- `ticket-supervisor`'s SKILL.md (§2) is unchanged. The five-step ticket loop,
  failure-adjudication ladder, retry caps, and commit-phase lock recipe are
  identical.

## Addendum: `/quick-fix` workflow (BP-600a-1, 2026-06-08)

The `/quick-fix` slash command was added as part of `EPIC-QuickFixWorkflow` to satisfy AC
`BP-600a-1` — the quick-fix workflow must operate in the current worktree without creating a new
worktree or switching branches. This is a direct application of this ADR's depth model:

- `/quick-fix` is the executing context (depth 0), equivalent to `/build-feature`.
- `ticket-supervisor` logic runs inline inside `/quick-fix` (no Agent-tool hop).
- Phase agents (`build-ac`, `test-writer`, `python-coder`, `test-runner`, `commit`) are
  spawned via the Agent tool at depth 1 — exactly as this ADR specifies.

The key difference from `/build-feature` is that `/quick-fix` never calls
`setup_ticket_worktree.py` and never runs `git worktree add`. All phases execute in the
directory where the command was invoked, on the branch that is already checked out. The
`git branch --show-current` value is invariant before and after the workflow.

Relevant contract: `templates/workflows-js/quick-fix.js` implements the entry point.

---

## References

- `tickets/00_inbox/epics/EPIC-FlattenSupervisorChain/Master_Plan.md` — the
  epic that implements this decision; all sub-tickets cite ADR-006 as rationale.
- `.claude/skills/building-epics/SKILL.md` §1.1 — the epic-level batching
  algorithm now inlined into `/build-feature`.
- `.claude/skills/building-epics/SKILL.md` §2 — the ticket-level dispatch loop
  implemented by `ticket-supervisor` (unchanged by this decision).
- `docs/architecture/agent_delivery_workflows.md` §5 — the `/quick-fix` workflow
  diagram and worktree-invariant contrast table documenting the current-worktree-only
  pattern (AC BP-600a-1).
- PR #22 (reverted) — the failed pass-through shim attempt that confirmed the
  depth-1 constraint is not bypassable within the Agent tool model.
