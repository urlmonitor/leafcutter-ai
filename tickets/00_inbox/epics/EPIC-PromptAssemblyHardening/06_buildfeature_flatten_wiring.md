---
title: "Wire /build-feature to the flattened script driver so phase-agent templates apply"
status: todo
components:
  - supervisor_system
  - build_pipeline
created: 2026-07-08
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
change_target: pipeline
risk_surface: internal
test_constraints: unit_only
complexity: high
ac_coverage: 0/7
files_touched:
  - templates/workflows-js/build-feature.js
  - unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
agents:
  architect-review: needed
  adr-author: needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 06: Wire /build-feature to the flattened script driver so phase-agent templates apply

## Actor / Goal

In order that phase-agent templates (python-coder, test-writer, sign-off, etc.)
actually take effect on the `/build-feature` path, `build-feature.js` must drive each
ready ticket's phases through the **flattened script driver** (`build-ticket.js`
semantics — one depth-1 `agent()` per needed phase) instead of dispatching a single
`ticket-supervisor` agent that, at depth 1, cannot spawn phase agents and therefore
executes every phase inline under no phase template.

## Context

Verified from the executed workflow script and transcripts during
EPIC-PromptAssemblyHardening (2026-07-08):

- `templates/workflows-js/build-ticket.js` is the flattened driver — it loops over
  needed phases and dispatches each as `agent(prompt, { agentType: phaseName })`
  (lines ~255–267), so each phase runs under its own template.
- `templates/workflows-js/build-feature.js` does **not** call it. Both the epic-batch
  path (line ~311) and the single-ticket path (line ~398) dispatch
  `agent("Drive ticket to completion … Execute all needed phase agents in order.",
  { agentType: "ticket-supervisor" })`, and the header explicitly notes "workflow()
  is NOT called."
- Because the supervisor is spawned at depth 1 and Claude Code caps sub-agents at
  depth 1, it cannot spawn phase agents (depth 2). In the observed build, all 5
  ticket-supervisors ran every phase **inline** (zero Agent/Task calls) — no
  phase-agent template loaded, and TDD separation collapsed (one agent wrote both
  tests and code).
- `build-ticket.js` was introduced alongside `build-feature.js` in PR #198 and has
  been **orphaned since creation** — nothing routes to it.

**Design decision (already constrained — ADR records it, does not re-open):** the fix
MUST **inline `build-ticket.js`'s phase-dispatch loop directly into `build-feature.js`**.
`build-feature.js` CANNOT `workflow('build-ticket', …)` because the Workflow tool
permits only depth-1 nesting — a `workflow()` call inside a running workflow throws
(this is the documented "E2 leaf-invariant" reason). Inlining keeps each phase agent
at depth 1 so its template applies. The ADR should record this decision and the
depth-1 rationale; architect-review confirms the inlined loop preserves batching,
dependency ordering, worktree-guard, and failure adjudication. To avoid divergence,
consider extracting the shared phase-loop so `build-ticket.js` and `build-feature.js`
use one implementation.

## AC References

Implements L1 **BO-2000f** and its leaves: BO-2000f-1, BO-2000f-2, BO-2000f-3,
BO-2000f-4, BO-2000f-4-i, BO-2000f-5, BO-2000f-5-i. Canonical source:
[docs/acceptance-criteria/build-orchestration/BO-2000-correct-prompts-by-construction/](../../../../docs/acceptance-criteria/build-orchestration/BO-2000-correct-prompts-by-construction/).

## Acceptance Criteria

- [ ] AC-1 (BO-2000f-1): the epic-batch path drives each ready ticket's phases through the flattened driver (per-phase depth-1 dispatch), not a single inline `ticket-supervisor` agent.
- [ ] AC-2 (BO-2000f-2): the single-ticket path routes phases through the same flattened driver.
- [ ] AC-3 (BO-2000f-3): a code ticket driven via `/build-feature` runs `test-writer` and the coder as SEPARATE phase agents (TDD separation preserved).
- [ ] AC-4 (BO-2000f-4): a structural regression check confirms `build-ticket.js` is reachable/invoked from `build-feature.js` and phase execution is not inlined via a whole-ticket `ticket-supervisor` dispatch.
- [ ] AC-5 (BO-2000f-4-i): that structural check FAILS if whole-ticket inline execution via `ticket-supervisor` is reintroduced.
- [ ] AC-6 (BO-2000f-5): the rewire preserves the worktree-guard, planner batching, dependency ordering, and failure adjudication.
- [ ] AC-7 (BO-2000f-5-i): dependency ordering is preserved — a ticket that `depends_on` another is not driven until the dependency completes.

## Test Requirements

```yaml
tests:
  - name: test_build_feature_routes_phases_through_flattened_driver
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    covers: [BO-2000f-1, BO-2000f-2, BO-2000f-4]
    asserts: "build-feature.js drives per-phase dispatch (via build-ticket driver / agentType phaseName) and does not dispatch agentType 'ticket-supervisor' for per-ticket phase execution."
  - name: test_structural_guard_fails_on_inline_supervisor
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    covers: [BO-2000f-4-i]
    asserts: "the structural check flags a build-feature variant that dispatches a whole-ticket ticket-supervisor for phase execution."
  - name: test_batching_and_dependency_order_preserved
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    covers: [BO-2000f-5, BO-2000f-5-i]
    asserts: "planner batching + depends_on ordering logic is retained after the rewire (a dependent ticket is not scheduled before its dependency)."
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_build_feature_flatten_wiring.py::test_bo2000f1_epic_batch_uses_flattened_driver | | |
| AC-2 | test_build_feature_flatten_wiring.py::test_bo2000f2_single_ticket_uses_flattened_driver | | |
| AC-3 | test_build_feature_flatten_wiring.py::test_bo2000f3_tdd_separation_test_writer_before_coder | | |
| AC-4 | test_build_feature_flatten_wiring.py::test_bo2000f4_structural_guard_positive | | |
| AC-5 | test_build_feature_flatten_wiring.py::test_bo2000f4i_structural_guard_flags_inline_supervisor | | |
| AC-6 | test_build_feature_flatten_wiring.py::test_bo2000f5_batching_and_orchestration_preserved | | |
| AC-7 | test_build_feature_flatten_wiring.py::test_bo2000f5i_dependency_ordering_preserved | | |

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [x] test-writer — 2026-07-09 10:45
- [x] python-coder — 2026-07-09 11:30
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-07-09 11:30 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  build_feature_js_rewired: true
  ticket_supervisor_dispatch_removed: true
  per_phase_dispatch_added: true
  phase_order_array_added: true
  batching_and_worktree_guard_preserved: true
  depends_on_ordering_preserved: true
  all_7_red_baseline_tests_green: true
  full_prompt_assembly_suite_33_tests_green: true
red_baseline_results:
  - test_name: test_bo2000f1_epic_batch_uses_flattened_driver
    result: green
  - test_name: test_bo2000f2_single_ticket_uses_flattened_driver
    result: green
  - test_name: test_bo2000f3_tdd_separation_test_writer_before_coder
    result: green
  - test_name: test_bo2000f4_structural_guard_positive
    result: green
  - test_name: test_bo2000f4i_structural_guard_flags_inline_supervisor
    result: green (was already green; synthetic snippet probe)
  - test_name: test_bo2000f5_batching_and_orchestration_preserved
    result: green
  - test_name: test_bo2000f5i_dependency_ordering_preserved
    result: green
Rewired templates/workflows-js/build-feature.js to inline the flattened per-phase driver from build-ticket.js. Removed both agentType: 'ticket-supervisor' dispatches (epic-batch path ~line 311 and single-ticket path ~line 398). Added: TICKET_PLANNER_SCHEMA, PHASE_RESULT_SCHEMA, CLASSIFY_SCHEMA, MAX_RETRIES, phaseOrder array (19 agents, test-writer at index 4 before python-coder at index 5), getPriority(), sortByCanonicalPriority(), and driveTicketPhases() async helper that inlines build-ticket.js Phase 1-3 semantics (per-ticket planner + sequential phase loop with failure adjudication + retry caps). Both epic-batch path (inside parallel() closures) and single-ticket path now call driveTicketPhases(). BATCH_SIZE, worktreeResult guard, and depends_on planner prompt preserved. JS syntax confirmed valid via node --check. All 33 prompt_assembly tests green; no regressions.

### 2026-07-09 10:45 — test-writer (status: ok)
feedback-id: fb_2026-07-09_039d18c9
completion_manifest:
  tests_written: true
  all_new_tests_red: true
  one_test_passes_immediately:
    result: false
    reason: "test_bo2000f4i_structural_guard_flags_inline_supervisor passes immediately — it uses a synthetic snippet (controlled input) to prove the guard helper detects the anti-pattern. It is informational (not a tautology) and is flagged in the red_baseline."
    remediation: "No action needed. The other 6 tests are the coders' RED targets. test_bo2000f4i will remain green before and after the fix."
  ac_coverage_table_filled: true
red_baseline:
  - test_name: test_bo2000f1_epic_batch_uses_flattened_driver
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    error: "AssertionError: True is not false : build-feature.js dispatches agentType: 'ticket-supervisor' for per-ticket phase execution on the epic-batch path. The epic batch loop must be rewired to the flattened per-phase driver (BO-2000f-1)."
  - test_name: test_bo2000f2_single_ticket_uses_flattened_driver
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    error: "AssertionError: True is not false : build-feature.js dispatches agentType: 'ticket-supervisor' for the single-ticket path. Both paths must use the flattened per-phase driver (BO-2000f-2)."
  - test_name: test_bo2000f3_tdd_separation_test_writer_before_coder
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    error: "AssertionError: -1 not greater than -1 : build-feature.js does not contain a phaseOrder array with 'test-writer'. The flattened driver must define a canonical phase ordering so test-writer runs before the coder (BO-2000f-3)."
  - test_name: test_bo2000f4_structural_guard_positive
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    error: "AssertionError: True is not false : Structural guard FAILED (BO-2000f-4): agentType: 'ticket-supervisor' found in build-feature.js for per-ticket phase execution."
  - test_name: test_bo2000f4i_structural_guard_flags_inline_supervisor
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    error: "(passes immediately — synthetic-snippet guard probe; informational only)"
    note: "passes immediately — may be under-specified; tests the guard helper on a controlled bad snippet, not the actual file state"
  - test_name: test_bo2000f5_batching_and_orchestration_preserved
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    error: "AssertionError: False is not true : build-feature.js does not contain the per-phase dispatch pattern (agentType: phaseName). The rewire must add this alongside the preserved batching logic and worktree guard (BO-2000f-5)."
  - test_name: test_bo2000f5i_dependency_ordering_preserved
    file: unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
    error: "AssertionError: False is not true : build-feature.js does not contain the per-phase dispatch pattern (agentType: phaseName). The rewire must implement flattened dispatch while preserving depends_on dependency ordering (BO-2000f-5-i)."

7 tests written (one per BO-2000f leaf AC). Verified RED via `python -m unittest` (exit code 1, 6 failures). The pytest run shows XFAIL instead of FAIL because the project's `pytest_ac_enforcement` plugin downgrades failures for not-done ACs to informational XFAIL — this is expected project behavior. The `python -m unittest` path (no plugin) gives the true RED state. Coder must rewire build-feature.js to inline the flattened per-phase dispatch loop (agentType: phaseName) for both the epic-batch and single-ticket paths, add the phaseOrder array listing test-writer before python-coder, and remove the agentType: 'ticket-supervisor' dispatch for per-ticket phase execution.

## Implementation Tasks

### architect-review / adr-author
- [ ] Decide and record (ADR) whether to `workflow('build-ticket')` per ticket vs inline the phase loop, resolving the "E2 leaf-invariant" constraint and confirming phase agents stay at depth 1.

### python-coder
- [x] Rewire `build-feature.js` per the ADR so per-ticket phase execution goes through the flattened driver; preserve worktree-guard, planner batching, dependency ordering, and failure adjudication.

## Risk & Safety

- Touches money? No.
- Touches data? No — changes a workflow driver script.
- Reversibility? Fully reversible via git. High blast radius (affects every `/build-feature` run), so gated behind ADR + architect-review + tests.
