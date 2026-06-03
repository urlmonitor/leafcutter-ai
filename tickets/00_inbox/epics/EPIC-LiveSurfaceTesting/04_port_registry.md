---
title: "Implement port registry module (scripts/port_registry.py) with CLI"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_adr_live_surface_testing.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/port_registry.py
  - leafcutter-ai/tests/test_port_registry.py
agents:
  architect-review: signed_off
  adr-author: not_needed
  test-writer: signed_off
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# 04: Implement port registry module (scripts/port_registry.py) + CLI

## Actor / Goal

In order to allow multiple concurrent worktrees to each start their own server
without port collisions, we need a `port_registry.py` module that maintains a
JSON file mapping worktree names to allocated ports, so that the
`live-surface-tester` agent and the worktree startup helper can request a free
port and release it atomically.

## Context

This ticket depends on 01 (ADR accepted). The ADR specifies:

- Registry is a JSON file at a project-local path (e.g.
  `.live_surface_testing/port_registry.json`, relative to the project root).
- Concurrent writes must be atomic — use a file lock (`fcntl.flock` on Linux/
  macOS, `msvcrt.locking` on Windows).
- Allocation draws from the range `[port_range_start, port_range_end]`
  configured in `skills_config.json → live_surface_testing`.
- Before allocating a port number, the registry does an OS-level `SO_REUSEADDR`
  bind probe to confirm the port is actually free on the host.

### Registry file schema

```json
{
  "allocations": {
    "<worktree_name>": {
      "port": 8201,
      "pid": 12345,
      "allocated_at": "2026-06-03T14:00:00Z"
    }
  }
}
```

`pid` is written by the startup helper (ticket 06) after the server starts. The
registry records `None` / absent `pid` until the server is up.

### CLI contract

```
python scripts/port_registry.py allocate <worktree_name> [--config-path <path>]
python scripts/port_registry.py release <worktree_name> [--config-path <path>]
python scripts/port_registry.py list [--config-path <path>]
python scripts/port_registry.py set-pid <worktree_name> <pid> [--config-path <path>]
```

- `allocate`: returns the allocated port number on stdout (integer, one line).
  If the worktree already has an allocation, returns the existing port
  (idempotent).
- `release`: removes the allocation entry. Exits 0 even if the entry is absent.
- `list`: prints the registry as JSON to stdout. Safe for human inspection.
- `set-pid`: records the server PID after startup. Used by the startup helper.

### Error conditions

- `allocate` when the entire port range is occupied: exit 1 with message
  `"port_registry: no free ports in range [start, end]"`.
- `allocate` when `skills_config.json → live_surface_testing.enabled` is
  `false`: exit 1 with `"port_registry: live_surface_testing is not enabled"`.

### Thread / process safety

Use `filelock` (PyPI: `filelock`) for cross-process locking. This is already
available in many Python environments. If absent, fall back to `fcntl.flock`
on POSIX and raise `NotImplementedError` on Windows with a clear message.

## Acceptance Criteria

```gherkin
Given the port range is 8200–8210
 And worktree "my-feature" has no existing allocation
When port_registry.py allocate my-feature is called
Then it prints a port number between 8200 and 8210 inclusive
 And the registry JSON file contains an entry for "my-feature"

Given worktree "my-feature" already has port 8202 allocated
When port_registry.py allocate my-feature is called again
Then it prints 8202 (same port, idempotent)
 And no new entry is created

Given the port range is 8200–8200 (only one port)
 And that port is already allocated to another worktree
When port_registry.py allocate new-feature is called
Then it exits with code 1
 And stderr contains "no free ports"

Given worktree "my-feature" has port 8202 allocated
When port_registry.py release my-feature is called
Then the registry JSON no longer contains an entry for "my-feature"
 And exit code is 0

Given the registry has no entry for worktree "other-feature"
When port_registry.py release other-feature is called
Then exit code is still 0 (idempotent release)

Given two concurrent allocate calls arrive simultaneously for different worktrees
When both calls complete
Then each call receives a different port number
 And the registry file is not corrupted
```

## Sign-offs

- [x] architect-review — 2026-06-03 10:00
- [x] test-writer — 2026-06-03 10:01
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-03 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-03_523ae39c
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

Impact classification: **SMALL**. Ticket creates 2 new files (`scripts/port_registry.py`, `leafcutter-ai/tests/test_port_registry.py`) within a single component (`build_pipeline`). No always-large triggers: no Alembic migration, no hypertable change, no public API change, no ADR contract change (ADR-007 already accepted and covers this design). File-count threshold: 2 ≤ 5. Component count: 1. No cross-module boundary crossing.

Architectural note: The design is already specified in ADR-007 (port registry as JSON file + file-level lock). The `filelock` PyPI dependency with POSIX `fcntl.flock` fallback is appropriate. The `SO_REUSEADDR` bind-probe before allocation is the correct approach for confirming port availability without races. The CLI subcommand pattern (`allocate`, `release`, `list`, `set-pid`) is clean and consistent with Unix conventions. One concern: the registry file path (`.live_surface_testing/port_registry.json`) differs slightly from the ADR's `config/live_surface_ports.json` — the ticket spec takes precedence as it was written after the ADR and refines the path. Ensure the test suite uses a temp directory for the registry file to avoid polluting the worktree during test runs.

Acceptance adjustments: none. ADR-007 decisions are settled and non-negotiable.

No new ADR needed. No diagrams needed (pure refactor within one component, no new service boundary).

## Escalation
Branch: none
Reason: 2 files in 1 component (build_pipeline); no always-large trigger fired.

### 2026-06-03 10:01 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket). No `## Test Requirements` YAML block found. python-coder will implement both module and tests per Implementation Tasks.

## Implementation Tasks

- [ ] Create `scripts/port_registry.py`:
  - `PortRegistry` class:
    - `__init__(config_path, registry_path)` — loads config from
      `skills_config.json`; determines registry file path
    - `allocate(worktree_name) -> int` — atomic, probes OS bind
    - `release(worktree_name) -> None` — atomic, idempotent
    - `set_pid(worktree_name, pid) -> None` — atomic
    - `list_allocations() -> dict` — read-only
    - `_probe_port_free(port) -> bool` — `SO_REUSEADDR` socket bind check
    - `_lock()` — context manager using `filelock` or `fcntl.flock`
  - `main()` CLI entry point using `argparse` with subcommands:
    `allocate`, `release`, `list`, `set-pid`
  - All external I/O wrapped per the project error-handling policy
    (Rule 1: wrap with specific exceptions; Rule 3: log + re-raise or wrap)
- [ ] Write `leafcutter-ai/tests/test_port_registry.py`:
  - Tests for all CLI commands (using `subprocess.run` to invoke the CLI)
  - Concurrent-allocation test using `concurrent.futures.ThreadPoolExecutor`
  - Idempotency tests for `allocate` and `release`
  - OS bind probe test (mock `socket.socket` to simulate port-in-use)

## Risk & Safety

- Touches money? No.
- Touches data? The registry file is ephemeral — it lives in
  `.live_surface_testing/` (gitignored). Losing it only means orphaned ports
  that the finalize-feature cleanup (ticket 07) will handle.
- Reversibility? The module is entirely new. Removing it and the registry file
  restores prior behaviour.
- Windows compatibility: `fcntl` is POSIX-only. The `filelock` PyPI package
  handles both; document the requirement. Raise `NotImplementedError` on
  Windows if `filelock` is absent so the failure is explicit.
