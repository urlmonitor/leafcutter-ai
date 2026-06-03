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
