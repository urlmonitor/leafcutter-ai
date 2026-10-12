---
title: "Decision records: a human ruling is staged with its own assessment basis, not as a kernel ranking"
status: todo
components:
  - decision_kernel
  - knowledge_management
created: 2026-10-08
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: schema
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: false
tags:
  - decision-kernel
  - decision-record
  - schema
  - trusted-asset
  - human-ruling
last_updated: 2026-10-08
files_touched:
  - kernel/memory/models.py
  - kernel/memory/builder.py
  - kernel/memory/staging.py
  - kernel/capabilities/decision/executor.py
  - config/decision_record.schema.json
  - knowledge/native_types/decision_schema.json
  - reports/native-fields/review-Decision.json
  - tests/knowledge/test_native_decision.py
  - tests/kernel/capabilities/test_choice_with_condition.py
  - docs/product-truth/mock-data/leafcutter/decisions.mock.json
  - docs/product-truth/flows/leafcutter/decision-forming.flow.json
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Decision records: a human ruling is staged with its own assessment basis, not as a kernel ranking

## Actor / Goal
In order that a published decision record says truthfully how the decision was reached, we need
a decision a human settled at a tie or escalation to be staged with assessment basis
`human_ruling` instead of `kernel_ranking` with an empty ranking. Then readers, precedent reuse
and the knowledge graph can tell a ruling apart from a ranked choice without parsing the
rationale text.

## Context
- **Current behaviour (PR #1003, TICKET-20261002-KernelChoiceWithCondition).** A human choice
  at an escalation resolves the decision with `design_reason` `human_ruling`
  (`kernel/capabilities/decision/approvals.py:27`, `design_ending.py:185`). The executor then
  stages it like any design choice: `_stage(ctx, work, result, basis="kernel_ranking")`
  (`kernel/capabilities/decision/executor.py:93`). `_stage` passes `cont.design_ranking`
  (:132), which is empty for an escalation because no ranking was shown. The record therefore
  claims `kernel_ranking` while holding no ranking.
  `tests/kernel/capabilities/test_choice_with_condition.py:338-347` pins this as documented
  current behaviour and names this follow-up.
- **The vocabulary.** `RecordAssessment.basis` is
  `Literal["kernel_ranking", "resolved_gate", "precedent_reuse"]` (`kernel/memory/models.py:107`).
  `builder._assessment` (`kernel/memory/builder.py:166-167`) coerces anything else to
  `kernel_ranking`, and `config/decision_record.schema.json` (`RecordAssessment.basis.enum`,
  about :308-316) is generated from the model.
- **The constraint.** `knowledge/native_types/decision_schema.json` is a byte-identical,
  hash-pinned trusted copy of that schema (verified identical on 2026-10-08).
  `tests/knowledge/test_native_decision.py:196-198` pins its sha256
  (`84471651…80e1c3`). `reports/native-fields/review-Decision.json` (reviewed 2026-10-02,
  `status` `reviewed_ready_for_coder`) embeds the exact reviewed schema and the same hash in its
  `authorities`. Adding an enum value therefore needs a re-review of that report and a re-pin,
  not only a code change. This is why PR #1003 left it out.
- **The product-truth contract.** `docs/product-truth/mock-data/leafcutter/decisions.mock.json`:
  - invariant :24 says `assessment_basis == 'kernel_ranking'` implies the options' kernel ranks
    are 1..n without gaps, `selected_rank` equals the selected option's rank and `confidence`
    equals its `required_mean`. A ruling staged as `kernel_ranking` with an empty ranking cannot
    meet it.
  - the field note :70 says "this dataset does not fix which basis value such a record carries".

  The `escalation-ruling` branch of `docs/product-truth/flows/leafcutter/decision-forming.flow.json`
  (about :4384 and the v11 note about :7023) describes `kernel_ranking` with an empty ranking as
  "current behaviour" and this change as a separate follow-up.
- **Published records.** `docs/decisions/` holds 11 records. None is a human ruling, so no
  published record changes value.
- Component note: `knowledge_management` owns the native Decision type and the review report.
  The re-review and re-pin follow that component's trusted-asset procedure (KM-400a-1-xv,
  KM-400a-3-i).

## Acceptance Criteria
- [ ] AC-1: `RecordAssessment.basis` accepts `human_ruling`. `builder._assessment` keeps it
  instead of coercing it, and `config/decision_record.schema.json` regenerated from the model
  lists it in `RecordAssessment.basis.enum`.
- [ ] AC-2: A tie escalation resolved by a human choice stages a record with
  `assessment.basis == "human_ruling"`, an empty `ranking`, and `selected_rank` and `confidence`
  null. A ranked design choice still stages `kernel_ranking` with its full ranking.
  `test_the_staged_basis_stays_kernel_ranking_with_an_empty_ranking` is replaced by a test that
  asserts this.
- [ ] AC-3: `knowledge/native_types/decision_schema.json` is byte-identical to the regenerated
  config schema. `reports/native-fields/review-Decision.json` is re-reviewed: a new
  `reviewed_on`, the new sha256 in `authorities`, and an updated `exact_reviewed_schema`.
  `test_native_decision.py` pins the new sha256 and passes.
- [ ] AC-4: In `decisions.mock.json`, `assessment_basis` lists `human_ruling`. A new invariant
  states that `human_ruling` implies no ranking, null `selected_rank` and `confidence`, a human
  `approved_by`, and a rationale opening with "Human ruling:". The `kernel_ranking` 1..n
  invariant is reviewed and either kept as it is or restated, with the reason recorded in the
  dataset's history. `validate_product_truth.py` passes.
- [ ] AC-5: The `escalation-ruling` branch of `decision-forming.flow.json` no longer calls
  `kernel_ranking` with an empty ranking the current behaviour. It names `human_ruling` as the
  staged basis, and the product-truth validator passes.
- [ ] AC-6: Every record in `docs/decisions/` still validates (`decisions validate`), and the
  existing kernel memory, capabilities and knowledge suites pass.

## Test Requirements

```yaml
tests:
  - name: test_a_tie_ruling_is_staged_with_basis_human_ruling
    location: tests/kernel/capabilities/test_choice_with_condition.py
    type: integration
    covers: [AC-2]
    description: |
      Replaces test_the_staged_basis_stays_kernel_ranking_with_an_empty_ranking: a tie answered
      with choice A stages basis human_ruling, empty ranking, null selected_rank and confidence.
  - name: test_a_ranked_choice_still_stages_kernel_ranking
    location: tests/kernel/capabilities/test_choice_with_condition.py
    type: integration
    covers: [AC-2]
    description: |
      The ranked design-choice path keeps basis kernel_ranking with its full ranking.
  - name: test_decision_complete_source_is_lossless_and_schema_pinned
    location: tests/knowledge/test_native_decision.py
    type: integration
    covers: [AC-3]
    description: |
      Existing test; the sha256 pin moves to the re-reviewed schema, and the schema enum
      contains human_ruling.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | schema regeneration check (`kernel/memory/validate.py` tests) | | |
| AC-2 | test_a_tie_ruling_is_staged_with_basis_human_ruling, test_a_ranked_choice_still_stages_kernel_ranking | | |
| AC-3 | test_decision_complete_source_is_lossless_and_schema_pinned | | |
| AC-4 | validate_product_truth.py | | |
| AC-5 | validate_product_truth.py | | |
| AC-6 | `decisions validate`; kernel and knowledge suites | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Model and builder: add `human_ruling`, stop coercing it, regenerate the config schema.
- [ ] Executor: stage `human_ruling` when the resolved decision's `design_reason` is
  `human_ruling`. Keep `kernel_ranking` for a ranked choice. Update `staging.py`'s docstring.
- [ ] Re-review `review-Decision.json`, copy the schema to `knowledge/native_types/`, re-pin the
  sha256.
- [ ] Product truth: extend the decisions dataset (mock-data-author) and update the flow branch
  text (flow-author).
- [ ] Tests above.

## Risk & Safety
- Touches money? No.
- Touches data? It adds an enum value to a shared, hash-pinned contract. Records already
  published keep validating. Readers that switch on `basis` must accept the new value. Today the
  only reader in code is the staging path itself.
- Reversibility: revert the commit and the re-pin together. A record staged with `human_ruling`
  in between would fail validation after a revert, so revert before any such record is published.

## Out of Scope
- Changing how a ruling resolves the decision, its rationale text or its report limitation.
- Precedent reuse rules for ruled decisions.
