---
title: "EPIC: Live Surface Testing Agent"
type: epic
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-06-03
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: true
---

# EPIC: Live Surface Testing Agent

## Goal

In order to close the gap between unit/integration test coverage and real
end-to-end observability, we need a new `live-surface-tester` phase agent that
spins up the running application (backend API and/or frontend), exercises key
endpoints or UI surfaces, and reports pass/fail back to ticket-supervisor —
without write access, so fixes are dispatched to the appropriate coder agents —
so that the build-feature lifecycle can detect regressions that only manifest
under a live server process.

## Context

The current ticket lifecycle drives test coverage through:

```
test-planner → test-writer → test-runner
```

This covers unit tests and integration tests that can be exercised entirely in
process. It does NOT cover:

- HTTP endpoints that only behave correctly when the application is running
  (middleware, auth, CORS, routing)
- Frontend routes that require a browser or headless render engine
- Race conditions or startup sequencing issues

The `user-surface-smoker` agent (priority 11.5) is related but distinct: it
performs regex-based assertions against stdout/stderr output of slash commands
and pre-commit hooks. It does not start a server process or issue HTTP requests.

This epic adds a **new phase agent** (`live-surface-tester`, priority 11.8)
that:

1. Reads a `## Live Test Fixtures` block from the ticket body
2. Allocates a unique port (from a project-managed port registry) for this
   worktree
3. Spawns the application using the command declared in `skills_config.json`
4. Issues HTTP or browser requests against the allocated port
5. Asserts response status, body, and headers
6. Tears down the server process unconditionally after assertion
7. Returns a structured pass/fail payload to ticket-supervisor

When the tester finds a failure, it returns `(status: blocker)` with a named
responsible agent (`python-coder` / `frontend-coder` / `sql-coder`).
Ticket-supervisor re-dispatches that coder; the tester never modifies code.

### Design decisions (settled — do not reopen)

- **Read-only agent**: `live-surface-tester` has no Edit/Write tools.
  It observes and asserts only. Fixes are delegated to coder agents.
- **Port registry**: a JSON file (managed by `python-coder` ticket 04)
  tracks `worktree_name → allocated_port`. Allocated ports survive until
  `/finalize-feature` releases them.
- **Project-level toggle**: `skills_config.json` key
  `live_surface_testing.enabled` (bool). When `false`, the agent is
  skipped for the entire project. Default: `false` (opt-in).
- **Ticket-level toggle**: frontmatter field `live_surface_test` (bool).
  `true` opts in; `false` / absent opts out. BA sets this automatically
  based on heuristics (ticket 03).
- **Conditional registration**: `live-surface-tester` is only emitted in
  the `agents:` map when `live_surface_test: true` in the ticket
  frontmatter AND `live_surface_testing.enabled: true` in
  `skills_config.json`. Double-gated to prevent unwanted spawns in
  library-only projects.
- **Phase priority 11.8**: runs after `user-surface-smoker` (11.5) and
  before `commit` (12). Both smoker agents must pass before the commit
  phase locks the worktree.
- **New agent — not an extension of user-surface-smoker**: the HTTP/browser
  invocation model is fundamentally different from the subprocess regex
  model. Extending the existing smoker would couple two orthogonal concerns.

### ADR cross-reference

An ADR is needed to record the port registry scheme and the read-only agent
constraint. See ticket 01 (`01_adr_live_surface_testing.md`).

## Architecture Plan

### Diagrams

- `agent_flow` diagram at `docs/architecture/components/live-surface-tester-dispatch.md` (parent: `docs/architecture/components/`)

### ADRs

- New ADR: "Live Surface Tester — port registry, read-only constraint, and
  conditional dispatch" — to be authored in ticket 01 before any implementation
  begins.

## Sub-ticket Table

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_adr_live_surface_testing.md](./01_adr_live_surface_testing.md) | Author ADR: port registry scheme + read-only agent constraint | `[ ]` |
| 02 | [02_agent_template.md](./02_agent_template.md) | Write `live-surface-tester` agent template + register in `agent_registry.json` | `[ ]` |
| 03 | [03_skills_config_toggle.md](./03_skills_config_toggle.md) | Add `live_surface_testing` config block to `skills_config.json` schema + build.py injection | `[ ]` |
| 04 | [04_port_registry.md](./04_port_registry.md) | Implement port registry module (`scripts/port_registry.py`) + CLI | `[ ]` |
| 05 | [05_ba_ticket_toggle.md](./05_ba_ticket_toggle.md) | Teach business-analyst heuristics for `live_surface_test` frontmatter field | `[ ]` |
| 06 | [06_worktree_startup_helper.md](./06_worktree_startup_helper.md) | Write worktree startup helper (spin-up, health-check, teardown) callable by `live-surface-tester` | `[ ]` |
| 07 | [07_finalize_port_cleanup.md](./07_finalize_port_cleanup.md) | Wire port release + orphan-process cleanup into `/finalize-feature` | `[ ]` |

## Revival (2026-07-10) — foundation re-landed + wiring/hardening tickets (BO-2100)

The original tickets 01–07 above describe the **foundation** (ADR, agent template,
port registry, startup helper, config toggle + validation). A deep review found the
feature was **phantom-done**: that foundation is well-built and tested, but nothing
ever dispatches the agent, so it never runs. On revival the foundation has been
**re-landed onto this branch** (`feat/live-surface-tester-revive`, commit `5f57a5fd`;
62 tests passing, ruff clean). The missing dispatch wiring plus several merge-blocker
defect fixes are captured as the approved AC tree **BO-2100**
(`docs/acceptance-criteria/build-orchestration/BO-2100-live-app-proof/`) and the
per-AC tickets below (one ticket per leaf AC, generated with `implemented_by`
back-refs in the store).

### Workstream A — Dispatch wiring: make it actually run (the phantom-done fix)
Agents: `llm-expert` (templates/skills), `frontend-coder` (build-ticket.js)

| Ticket | AC | Surface |
|--------|----|---------|
| [BO-2100a-1](./TICKET-20260710-BO-2100a-1.md) | BO-2100a-1 | BA injects `live-surface-tester: needed` into ticket `agents:` map when both toggles true |
| [BO-2100a-1-i](./TICKET-20260710-BO-2100a-1-i.md) | BO-2100a-1-i | agent absent from map when not both toggles true |
| [BO-2100a-2](./TICKET-20260710-BO-2100a-2.md) | BO-2100a-2 | `ticket-supervisor.md` Spawn Allowlist includes the agent |
| [BO-2100a-3](./TICKET-20260710-BO-2100a-3.md) | BO-2100a-3 | `build-ticket.js` phaseOrder inserts agent at 11.8 (between smoker and commit) |
| [BO-2100a-3-i](./TICKET-20260710-BO-2100a-3-i.md) | BO-2100a-3-i | ordering 11.5 < 11.8 < 12 preserved |
| [BO-2100a-4](./TICKET-20260710-BO-2100a-4.md) | BO-2100a-4 | `building-epics` natural dispatch order references the agent |

### Workstream B — Toggle gate & safe default
Agents: `llm-expert` (authoring gate), `python-coder` (runtime default)

| Ticket | AC | Surface |
|--------|----|---------|
| [BO-2100b-1](./TICKET-20260710-BO-2100b-1.md) | BO-2100b-1 | project-off ⇒ never dispatched |
| [BO-2100b-1-i](./TICKET-20260710-BO-2100b-1-i.md) | BO-2100b-1-i | **fix:** `port_registry._is_enabled()` defaults **false** when key absent |
| [BO-2100b-2](./TICKET-20260710-BO-2100b-2.md) | BO-2100b-2 | ticket-off/absent ⇒ skipped |
| [BO-2100b-3](./TICKET-20260710-BO-2100b-3.md) | BO-2100b-3 | both-on ⇒ runs |

### Workstream C — Lifecycle cleanup & teardown  (`python-coder`)

| Ticket | AC | Surface |
|--------|----|---------|
| [BO-2100c-1](./TICKET-20260710-BO-2100c-1.md) | BO-2100c-1 | server PID recorded via `port_registry set-pid` (covers existing behavior) |
| [BO-2100c-2](./TICKET-20260710-BO-2100c-2.md) | BO-2100c-2 | finalize releases port + kills recorded PID |
| [BO-2100c-3](./TICKET-20260710-BO-2100c-3.md) | BO-2100c-3 | **fix:** teardown kills the whole process group (`start_new_session`/`killpg`) |
| [BO-2100c-3-i](./TICKET-20260710-BO-2100c-3-i.md) | BO-2100c-3-i | orphan-scan no over-kill / PID-reuse guard |

### Workstream D — Fail-loud & safety  (`python-coder`)

| Ticket | AC | Surface |
|--------|----|---------|
| [BO-2100d-1](./TICKET-20260710-BO-2100d-1.md) | BO-2100d-1 | **fix:** loud error when `requests` missing (no silent always-timeout) |
| [BO-2100d-2](./TICKET-20260710-BO-2100d-2.md) | BO-2100d-2 | `ConfigValidationError` on enabled + empty `startup_command` (covers existing) |
| [BO-2100d-3](./TICKET-20260710-BO-2100d-3.md) | BO-2100d-3 | worktree path resolution (`.leafcutter` not `.claude`) |

### Workstream E — Behavioral proof: the closure gate  (`test-runner`)

| Ticket | AC | Surface |
|--------|----|---------|
| [BO-2100e-1](./TICKET-20260710-BO-2100e-1.md) | BO-2100e-1 | drive a real `live_surface_test:true` ticket through ticket-supervisor and assert the agent **actually spawns** (not a synthetic test). **depends_on** A + C. |

### Docs & diagrams  (`documentation-expert` / `architecture-diagram-author`)
[BO-2100a-5](./TICKET-20260710-BO-2100a-5.md), [a-6](./TICKET-20260710-BO-2100a-6.md),
[b-4](./TICKET-20260710-BO-2100b-4.md), [b-5](./TICKET-20260710-BO-2100b-5.md),
[c-4](./TICKET-20260710-BO-2100c-4.md), [d-4](./TICKET-20260710-BO-2100d-4.md) —
sequence/component diagrams, how-to, and reference updates per each L1's documentation triggers.

**Build order:** Workstreams A + B + C + D (independent, parallel-safe by files) →
Docs → **E last** (the anti-phantom-done proof gate).

## Parallelism Notes

- Ticket 01 (ADR) must complete before any others begin — decisions not yet
  finalised.
- Tickets 03, 05 can begin after 01 (they don't depend on the implementation).
- Ticket 04 (port registry) depends on the scheme recorded in 01.
- Ticket 02 (agent template) depends on 01 and should reference 04's registry
  API.
- Ticket 06 (startup helper) depends on 02 and 04.
- Ticket 07 (finalize cleanup) depends on 04 and 06.

## Risk & Safety

- Touches money? No.
- Touches data? No production data. The live-surface-tester spins up a local
  process against a test database/fixture; it does not target production.
- Port collisions: the port registry guards against this, but the guard is only
  as reliable as the registry file's freshness. Mitigation: the startup helper
  does an OS-level bind check before reporting the port as allocated.
- Orphaned processes: if the tester crashes before teardown, the server process
  remains. Mitigation: the finalize-feature cleanup (ticket 07) scans and kills
  any PID registered in the port registry, and `skills_config.json`
  `worktree_cleanup.kill_residual_processes: true` already signals intent.
- Reversibility: the new `live-surface-tester` is additive. Setting
  `live_surface_testing.enabled: false` in `skills_config.json` disables the
  entire feature with no code changes. All new files are isolated under
  `templates/agents/` and `scripts/`.
