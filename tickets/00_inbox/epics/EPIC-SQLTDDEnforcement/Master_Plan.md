---
title: "EPIC: SQL TDD Enforcement"
type: epic
status: todo
components:
  - build_pipeline
created: 2026-05-27
depends_on: []
priority: medium
---

# EPIC: SQL TDD Enforcement

## Summary

Extend the TDD workflow enforcement introduced in `EPIC-TDDWorkflowEnforcement`
(Python-only, Phase 1) to cover SQL tests. The goal is to flip `sql-test-writer`
to run before `sql-coder`, making SQL tests the contract that drives SQL
implementation — mirroring the Python TDD flow.

## Predecessor

This epic is the direct follow-on to `EPIC-TDDWorkflowEnforcement`. That epic:
- Flipped `test-writer` to priority 5 (before `python-coder` at priority 6) for Python.
- Added the `red_baseline` contract: test-writer captures failing tests; coders make them green.
- Added the three-layer contract-shrinking guard (pre-commit hook, supervisor warn, honor-system).
- Explicitly descoped SQL TDD to this follow-on epic.

See [ADR-027](../../../docs/architecture/adrs/ADR-027-tdd-workflow-enforcement.md) for
the formal decision record. See `tickets/99_done/EPIC-TDDWorkflowEnforcement/` for the
completed predecessor epic.

## Scope

1. **Priority adjustment**: Assign `sql-test-writer` a priority less than `sql-coder` (currently 7) — e.g. priority 6.5 or restructure as priority 6 with `sql-coder` moved to 7.5. Update `config/agent_registry.json`.

2. **`is_ticket_phase` flag**: `sql-test-writer` currently has `is_ticket_phase: false`. To be dispatched by `ticket-supervisor` in the normal phase ordering, it must be set to `true`.

3. **sql-test-writer rewrite**: Mirror the changes made to `test-writer` in EPIC-TDDWorkflowEnforcement:
   - Update description to reflect test-FIRST role.
   - Add `red_baseline` capture schema to sign-off contract.
   - Add docs-only / config-only skip rule for SQL tickets.

4. **sql-coder success gate**: The `red_baseline` reading instruction is already in `sql-coder.md` (added in EPIC-TDDWorkflowEnforcement). Verify it references `sql-test-writer`'s baseline correctly.

5. **Contract-shrinking hook extension**: `check_contract_shrinking.py` currently detects Python test weakening. Extend it to cover SQL test files (if SQL tests are in `.py` wrappers under `unit_tests/sql_functions/`, they are already covered; if they are `.sql` test files, add detection logic).

6. **Documentation updates**: Update `docs/explanation/tdd-workflow.md` to remove the "Python-only Phase 1" qualifier and describe the full Python+SQL TDD flow. Update ADR-027 or author ADR-005 if the SQL TDD decision has materially different trade-offs.

## Key Design Decisions

The following architectural decisions must be made before sub-tickets are authored:

- **How to assign `sql-test-writer` a priority less than 7?** Option A: reuse priority 5 (concurrent with `test-writer`, safe for SQL-only tickets). Option B: introduce a new priority slot (e.g. 5.5) dedicated to SQL test authoring. Option C: make `sql-test-writer` and `sql-coder` a coupled pair that `ticket-supervisor` dispatches as a unit. Decision affects `agent_registry.json` structure.

- **How to handle tickets that need both Python and SQL TDD?** The current system runs `test-writer` (Python tests) before `python-coder`, and `sql-test-writer` (SQL tests) before `sql-coder`. For a ticket that has both Python and SQL implementation, both test-writer agents must complete before either coder starts. This requires the `ticket-supervisor` to enforce a two-stage pre-coder gate. Confirm whether this is in scope for this epic or a separate ticket.

## Sub-tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| (to be authored) | — | Sub-tickets to be created via `/create-epic` or `/create-ticket` | `[ ]` |

## Out of Scope

- Python TDD enforcement (already in `EPIC-TDDWorkflowEnforcement`).
- The `sql-coder` contract-shrinking prohibition honor-system clause (already added in EPIC-TDDWorkflowEnforcement).
- Changes to `sql-query` (read-only SQL authoring — not subject to TDD ordering).
