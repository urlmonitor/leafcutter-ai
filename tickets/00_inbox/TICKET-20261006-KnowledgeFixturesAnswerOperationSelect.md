---
title: "Knowledge kernel fixtures answer the operation-select question"
status: todo
components:
  - knowledge_management
created: 2026-10-06
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
test_constraints: unit_only
tags:
  - knowledge
  - test-fixtures
  - jev
last_updated: 2026-10-06
files_touched:
  - tests/knowledge/test_kernel_run.py
  - tests/knowledge/test_query_answer_contract_acceptance_kernel.py
  - integrations/README.md
agents:
  test-writer: needed
  python-coder: not_needed
  commit: needed
---

# Knowledge kernel fixtures answer the operation-select question

## Actor / Goal
In order to keep CI green and keep the knowledge kernel tests meaningful, we need the two
stale kernel fixtures to answer the `knowledge.operation_select` / `operation` Jev question
that every natural-language retrieval now asks, so that their graph reads run again and a
future bypass of the selector is caught by a test.

## Context
- **The behaviour change.** #1008 (commit 19e195bfa, merged 3ec14b85d, 2026-10-04) routes every
  natural-language retrieval through a Jev question, `knowledge.operation_select` / `operation`.
  `integrations/knowledge_execution.py` calls `assess_graph_operation` whenever
  `payload.knowledge is None`; `integrations/graph_selection.py` defines the question. This is
  intended: DK-300d-4 and DK-300d-4-i are done.
- **The stale fixtures.** The ScriptedJev of these fixtures never scripts that question, so every
  retrieval child fails with `invalid_provider_response: no scripted answer for
  knowledge.operation_select/operation` and no graph read runs:
  - `tests/knowledge/test_kernel_run.py` (`TestKnowledgeRun`);
  - `tests/knowledge/test_query_answer_contract_acceptance_kernel.py` (`TestPublicKernelAnswerContract`).
  #1008 updated the sibling `tests/knowledge/test_kernel_bridge.py` but missed these two.
- **Failing under `AC_ENFORCE_STRICT=1` (as CI runs them):**
  - `test_kernel_run.py::TestKnowledgeRun::test_full_run_persists_attributable_knowledge_evidence`
    (run BLOCKED instead of waiting for the host);
  - four `TestPublicKernelAnswerContract` tests (run status `partial`, no retrieval call):
    `test_research_obligations_reach_actual_retrieval_and_persist`,
    `test_scripted_sufficient_judgment_cannot_upgrade_unresolved_answer`,
    `test_foreign_evidence_diagnosis_compares_actual_scope_and_withholds_evidence`,
    `test_missing_fact_diagnosis_does_not_invent_remote_trace_or_root_cause`.
- **The fix.** Each fixture's `setUp` scripts the selector explicitly:
  `self.jev.script("knowledge.operation_select", "operation", choice_answer("get_component_context"))`.
  This is the binding the pre-#1008 code applied. It is NOT added to the shared `ScenarioCase`
  (`tests/kernel/integration/scenario_support.py`), where it would hide selector regressions in
  every scenario.
- Related ACs: DK-300d-4 and DK-300d-4-i (selection); the affected tests cover KM-400e-3,
  KM-500e-1 and KM-500g-2. No AC is amended.

## Acceptance Criteria
- [ ] AC-1: With `AC_ENFORCE_STRICT=1`, the five tests listed in Context pass.
- [ ] AC-2: Each of the two fixtures scripts the selector explicitly in its `setUp` with
  `get_component_context`; the shared `ScenarioCase` is unchanged.
- [ ] AC-3: No assertion is removed or loosened in either test file.
- [ ] AC-4: At least one test asserts the selection happened (a `knowledge.operation_select`
  batch was asked AND the persisted `knowledge_selected_operation` diagnostic equals
  `get_component_context`), so a future bypass of DK-300d-4 fails.
- [ ] AC-5: The Maintenance section of `integrations/README.md` names `tests/knowledge/` and
  strict mode (`AC_ENFORCE_STRICT=1`) for bridge changes.
- [ ] AC-6: No production code changes (only the two test files, `integrations/README.md` and
  this ticket change).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Test Requirements

```yaml
tests:
  - name: test_full_run_persists_attributable_knowledge_evidence
    location: tests/knowledge/test_kernel_run.py
    type: behavioral
    covers: KM-400e-3
    description: |
      Existing test, kept intact. Additionally asserts, right after start_run, that a
      knowledge.operation_select batch was asked and that the persisted
      knowledge_selected_operation diagnostic is get_component_context. Removing the fixture's
      selector script makes this new assertion fail first.
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Script `knowledge.operation_select` / `operation` -> `get_component_context` in
  `TestKnowledgeRun.setUp` (import `choice_answer` from `kernel.providers.fakes`).
- [ ] Script the same in `TestPublicKernelAnswerContract.setUp` (`choice_answer` already imported).
- [ ] Add the selection assertion (batch asked + persisted diagnostic) to
  `test_full_run_persists_attributable_knowledge_evidence`.
- [ ] Update the Maintenance section of `integrations/README.md`.
- [ ] Verify: strict-mode pytest over the three `tests/knowledge/` bridge files; mutation check
  (remove the script line, see the new assertion fail, restore); ruff.

## Out of Scope
- Any production change to `integrations/` or `kernel/`.
- Scripting the selector in the shared `ScenarioCase`.

## Risk & Safety
- Touches money? No.
- Touches data? No. Test fixtures and one README paragraph only.
- Reversibility? Fully reversible; no runtime behaviour changes.
