---
title: "ADR-007: Live Surface Tester — Port Registry, Read-Only Constraint, and Conditional Dispatch"
type: "adr"
status: "accepted"
created: "2026-06-03"
last_updated: "2026-06-03"
components:
  - build_pipeline
  - config_loader
related_docs:
  - tickets/00_inbox/epics/EPIC-LiveSurfaceTesting/01_adr_live_surface_testing.md
related_code: []
---

# ADR-007: Live Surface Tester — Port Registry, Read-Only Constraint, and Conditional Dispatch

## Status

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-03 |
| **Author** | EPIC-LiveSurfaceTesting / adr-author |
| **Supersedes** | — |

## Context

The leafcutter-ai agentic build pipeline includes a phase agent (`user-surface-smoker`,
priority 11.5) that verifies observable side-effects by invoking a running application
surface after `pr-reviewer` approves changes and before `commit` locks the worktree.
`user-surface-smoker` confirms that the surface is reachable and returns expected
responses, but it has no HTTP capabilities of its own — it relies on the server already
being up.

The pipeline needs a complementary agent, `live-surface-tester`, that actively drives an
HTTP surface via HTTP requests and asserts observable side-effects in a structured way.
This agent runs at priority 11.8 — after `user-surface-smoker` (11.5) and before
`commit` (12) — so that any surface-level failures discovered after smoke-testing can
block the commit before code is finalised in version control.

To support multi-worktree development (where multiple epics run concurrently in separate
worktrees on different ports), the agent needs a mechanism for discovering which port a
given worktree's development server is listening on. Without such a mechanism, either
all worktrees share the same port (collision risk) or each worktree hard-codes a port
(no collision detection).

Three design questions required settled answers before implementation could begin:

1. **How does `live-surface-tester` discover the server port for its worktree?**
2. **Can `live-surface-tester` modify the codebase or ticket state to self-repair issues it finds?**
3. **When should `live-surface-tester` be dispatched vs. skipped?**

This ADR records the settled decisions on all three questions. These decisions were made
by the EPIC-LiveSurfaceTesting planning phase and are not open for re-litigation during
implementation.

## Decision

### Decision 1 — Read-Only Agent

`live-surface-tester` MUST be a **read-only agent**: it has no `Edit` or `Write` tools.

The agent's sole output is its sign-off status and the comment it appends to the ticket.
If a test fails, the agent emits a `(status: blocker)` comment and allows
`ticket-supervisor`'s failure-adjudication ladder to route the finding to the appropriate
human or coder agent. The tester MUST NOT attempt to fix problems it discovers.

This preserves the separation of concerns: testing surfaces observe and report; coding
agents fix. Allowing the tester write access would couple two orthogonal concerns and
create a feedback loop in which the tester modifies the codebase, then must re-test its
own modification — an unbounded retry risk with no human checkpoint.

### Decision 2 — Port Registry

Port assignments for running development servers MUST be tracked in a **JSON file keyed
by worktree name**:

```
<worktree_root>/config/live_surface_ports.json
```

Schema:
```json
{
  "<worktree_name>": <port_number>,
  ...
}
```

- `<worktree_name>` is the directory name of the worktree (e.g. `EPIC-LiveSurfaceTesting`).
- `<port_number>` is an integer in the range 8100–8199 (the reserved live-surface-tester range).

The port registry is a shared mutable state file. Writes to it MUST use a file-level lock
(`fcntl.flock` on POSIX) to prevent corruption from concurrent worktree operations. The
lock is held only for the duration of the read-modify-write cycle; it is never held across
an HTTP request.

When a worktree starts its development server, it registers its port by writing to this
file. When the server stops, it de-registers by removing its entry. `live-surface-tester`
reads the registry at invocation time to discover the port; it never modifies the registry.

### Decision 3 — Project-Level Toggle

Projects that do not expose a runnable HTTP surface (pure libraries, CLI-only tools,
data-pipeline packages) MUST be able to opt out of live surface testing entirely.

The opt-out is controlled by a field in `skills_config.json` at the project root:

```json
{
  "live_surface_testing": {
    "enabled": false
  }
}
```

When `live_surface_testing.enabled` is `false` (or the field is absent), `live-surface-tester`
MUST be skipped for every ticket in the project and its `agents:` entry MUST be set to
`not_needed` by `business-analyst` at ticket-creation time.

### Decision 4 — Ticket-Level Toggle

Individual tickets may override the project-level setting to skip live surface testing for
a specific change (e.g. a pure documentation ticket or a migration with no surface impact).

The override is a boolean frontmatter field:

```yaml
live_surface_test: false
```

When this field is `false`, `ticket-supervisor` MUST skip `live-surface-tester` for that
ticket, regardless of the project-level setting. When the field is `true` or absent (and
the project-level setting is enabled), `live-surface-tester` runs normally.

### Decision 5 — Phase Priority 11.8

`live-surface-tester` MUST run at **phase priority 11.8** in the canonical phase ordering
defined in `ticket-supervisor`:

| Priority | Agent |
|---|---|
| 11 | `pr-reviewer` |
| 11.5 | `user-surface-smoker` |
| **11.8** | **`live-surface-tester`** |
| 12 | `commit` |

This ordering guarantees:
- `pr-reviewer` has already approved the change before the surface is tested.
- `user-surface-smoker` has already confirmed the surface is reachable before `live-surface-tester` makes HTTP assertions.
- A surface-level failure discovered by `live-surface-tester` blocks the commit (priority 12) from running, preventing untested code from being finalised in version control.

## Alternatives Considered

### Alternative A — Extend `user-surface-smoker` with HTTP Capabilities

Add HTTP assertion capabilities directly to `user-surface-smoker` so a second agent is
not required.

**Rejected.** `user-surface-smoker` and `live-surface-tester` have orthogonal concerns:
`user-surface-smoker` is a lightweight reachability probe (does the surface respond at
all?); `live-surface-tester` is a structured HTTP assertion layer (does the surface
return the correct data for a given request?). Coupling them in one agent conflates smoke
testing with acceptance testing and would require `user-surface-smoker` to carry HTTP
client dependencies and assertion logic that belong in a specialised tool. The existing
`user-surface-smoker` design also has no subprocess model — it cannot manage a
persistent HTTP session across multiple assertions.

### Alternative B — Shared Port Range Without a Registry

Assign each worktree a port from the shared range 8100–8199 at server start time, using
a simple first-available scan — no registry file.

**Rejected.** A first-available scan is not collision-safe across concurrent worktrees.
Two worktrees starting simultaneously can both scan the range, both find port 8100 free,
and both attempt to bind it. The second bind fails with a non-descriptive OS error. A
shared registry with file-lock semantics ensures that port assignment is serialised and
auditable: any worktree can inspect the registry to see which ports are in use and by
whom.

### Alternative C — Giving `live-surface-tester` Write Access for Self-Repair

Allow `live-surface-tester` to make minor fixes to the codebase (e.g. update a
hard-coded URL, add a missing route) when its assertions reveal a straightforward
discrepancy.

**Rejected.** An agent that both tests and fixes violates the separation of concerns
that makes the pipeline's failure-adjudication ladder reliable. If the tester modifies
code, it must re-test its own modification — creating an unbounded loop with no human
checkpoint. The parity guard and commit-phase serialisation lock are also designed around
the invariant that only designated coder agents write to source files; a tester with
write access bypasses this invariant. All findings are surfaced via `(status: blocker)`
comments; the repair is the responsibility of the appropriate coder agent, which can be
dispatched by `ticket-supervisor`'s failure-adjudication ladder after human review.

## Consequences

### Positive

- **No collision across concurrent worktrees.** The port registry with file-lock semantics
  eliminates the race condition present in a scan-only approach.
- **Projects with no HTTP surface are not penalised.** The project-level toggle
  (`live_surface_testing.enabled: false`) means pure library and CLI projects incur
  zero overhead from the live surface tester.
- **Ticket-level granularity.** The `live_surface_test: false` frontmatter field lets
  teams skip the phase for documentation-only or migration tickets without changing the
  project-wide setting.
- **Testing and repair remain decoupled.** The read-only constraint ensures that surface
  failures produce actionable blocker comments rather than opaque self-repair loops.
  Human review remains in the loop before any fix is committed.

### Negative

- **Port registry is shared mutable state.** Concurrent worktree writes require a
  file-level lock. If the lock is held by a crashed process, a stale lock may block
  new registrations until it is cleared manually. Mitigation: the lock is released by a
  `finally` block; the registry consumer (`live-surface-tester`) is read-only and never
  holds the lock.
- **`live-surface-tester` cannot self-repair.** A surface failure discovered at
  priority 11.8 halts the commit phase and requires a coder respawn, adding latency to
  the build pipeline. This is the intended behaviour — surface failures should block
  commits — but teams should be aware that a failing surface will pause an otherwise
  complete ticket.
- **Port range 8100–8199 is reserved.** Projects that already use ports in this range
  for other services will experience a conflict. Teams must either reassign their existing
  service ports or configure the live-surface-tester range to a different band.

### Neutral

- The `live-surface-tester` agent template and its port-discovery logic are implemented
  in subsequent EPIC-LiveSurfaceTesting tickets. This ADR defines the design contracts;
  those tickets implement them.
- The `ticket-supervisor` canonical phase ordering table must be updated to include
  priority 11.8. This is a documentation edit, not a behavioural change.

## References

- `tickets/00_inbox/epics/EPIC-LiveSurfaceTesting/01_adr_live_surface_testing.md` — the
  ticket that commissioned this ADR.
- `tickets/00_inbox/epics/EPIC-LiveSurfaceTesting/Master_Plan.md` — the five settled
  decisions that this ADR formally records.
- `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` — the flattened
  supervisor chain within which `live-surface-tester` runs at depth 1.
- `.claude/skills/building-epics/SKILL.md` §2 (Canonical Phase Ordering) — the phase
  priority table where priority 11.8 must be added.
