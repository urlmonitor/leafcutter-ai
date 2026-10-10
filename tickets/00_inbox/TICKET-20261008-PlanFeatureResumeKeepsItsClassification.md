---
title: "/plan-feature resume keeps the paused run's product-truth classification and never drops the owner's answer"
status: todo
components:
  - ux_prototyping
  - ac_driven_dev
created: 2026-10-08
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - plan-feature
  - product-truth
  - pause-resume
  - adr-024
  - nondeterminism
last_updated: 2026-10-08
files_touched:
  - templates/workflows-js/plan-feature.js
  - unit_tests/test_plan_feature_pt_phase.py
  - docs/product-truth/classifier/eval.jsonl
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

# /plan-feature resume keeps the paused run's product-truth classification and never drops the owner's answer

## Actor / Goal
In order that an owner's answer at a product-truth gate is the answer the run acts on, we need
a resumed `/plan-feature` run to reuse the classification and stage list of the run it resumes
instead of asking the classifier again, so that the resume continues at the gate the owner
answered and an answer that cannot be applied is reported instead of silently lost.

## Context
- **Observed 2026-10-08.** Same request, two runs:
  - `wf_fc30286f-e12` (first run): `pt-classifier` returned `full-set` (flow, mock data and
    mockup). `mock-data-author` drafted, and the run paused at `pt-gate-mockdata`.
  - `wf_424216d0-185` (resume, `resume_answer` for `pt-gate-mockdata`, an **edit** with
    feedback): `pt-classifier` returned `mockup-only` (`needs_flow` false, `needs_mock_data`
    false). The mock-data stage was not in the new stage list, so the edit was never applied.
    The run went straight to `mockup-author` and paused again at `pt-gate-mockup`. Nothing told
    the owner that the answer had been dropped.
  - `needs_flow: false` is also wrong on its face. The request says it extends an existing
    flow, and `templates/agents/pt-classifier.md` (the `needs_flow` bullet, about :91-93) says
    "or an extension of an existing journey" counts as a flow. The same prompt therefore gave
    two different answers, and the second one contradicts the prompt's own rule.
- **Why it happens.** In `templates/workflows-js/plan-feature.js`:
  - An ADR-024 resume is a fresh invocation, so every `agent()` call runs again. The PT phase
    dispatches `pt-classifier` unconditionally at its start (:2760-2769) and derives the stage
    list from that new answer (`derivePtRunSet`, :1086, :2778).
  - The PT gate's pause context is only `{ stage: ptStep.stage }` (:2870). The classifier
    decision and stage list of the paused run are not persisted, so they cannot be reused.
  - `resolveGate` (:1642) applies `args.resume_answer` only when its `gate_id` equals the gate
    being resolved (:1650). Otherwise it falls through to `pauseAtGate` (:1808), which
    overwrites the pause record with the new gate. An answer for a gate the run never reaches
    is dropped without a trace.
- **The same seam has a sibling gap.** The AC-authoring loop already skips re-authoring on a
  resume that moves past its gate (`peekPausedGateId` :1596, `skipAuthorOnResume` :3104-3134,
  `_resumedContext` :1711-1714, from ACD-2100c-3 / ACD-2100c-3-i). The PT loop (:2803-2939) has
  none of this. On an **approve** resume it re-dispatches the PT author before resolving the
  gate, so it commits a new draft the owner never saw.
- **ACs this brings into line.** ACD-2100c-3 (done) says a resumed run "continues from that
  decision point rather than repeating the steps before it", and that "the answer supplied is
  the one applied to that decision". This holds today for the AC gates but not for the PT gates.
  UXP-544 (the classifier is dispatched once per run) and UXP-549 (crash-resume skips committed
  PT stages) are unchanged.
- **Size.** `plan-feature.js` measures 2959 lines against the 1000-line `.js` limit
  (check-file-size, 2026-10-08), so the ratchet applies: the change must leave the file shorter
  than at HEAD. Move the PT resume logic into a helper the file already imports from, or extract
  one.

## Acceptance Criteria
- [ ] AC-1: When a PT gate pauses, its pause record's `context` holds the classifier decision
  (`outcome`, the three `needs_*` booleans, `component`, `entities`), the derived stage list in
  run order, the paused `stage`, and the artifact paths the stage's author reported.
- [ ] AC-2: On a resume whose pause record holds a classifier decision, `pt-classifier` is not
  dispatched. The stage list comes from the persisted decision. A harness run whose classifier
  stub would answer `mockup-only` on a second dispatch shows zero `pt-classify` dispatches on
  resume and runs the mock-data stage.
- [ ] AC-3: The 2026-10-08 replay: first run `full-set`, paused at `pt-gate-mockdata`, resumed
  with a person-attributed `edit` and feedback `F`. `mock-data-author` is re-dispatched with `F`
  in its prompt before any `mockup-author` dispatch.
- [ ] AC-4: On a resume with `approve` or `cancel` at a PT gate, that stage's author is not
  re-dispatched. `approve` commits exactly the artifact paths recorded in the pause context, and
  their bytes are unchanged between pause and commit.
- [ ] AC-5: If a resumed run's `resume_answer` names a gate that is not the gate in the pause
  record, or a gate the run's stage list does not contain, the run dispatches no PT authoring
  agent and leaves the pause record unchanged. It returns a terminal payload with status
  `resume_answer_not_applied` that names the answer's `gate_id` and the gate the run is paused at.
- [ ] AC-6: `docs/product-truth/classifier/eval.jsonl` gains a row for a request that extends an
  existing flow, expecting `needs_flow: true`. The row conforms to `classifier-eval.schema.json`.

## Test Requirements

```yaml
tests:
  - name: test_pt_pause_context_carries_classification_and_stage_list
    location: unit_tests/test_plan_feature_pt_phase.py
    type: behavioral
    covers: [AC-1]
    description: |
      Drive the workflow to pt-gate-mockdata with a full-set classifier stub and read the
      persisted pause record: its context holds outcome, needs_* booleans, component, entities,
      the ordered stage list and the reported artifact paths.
  - name: test_resume_does_not_reclassify_and_applies_mockdata_edit
    location: unit_tests/test_plan_feature_pt_phase.py
    type: behavioral
    covers: [AC-2, AC-3]
    description: |
      First run full-set, pause at pt-gate-mockdata. Resume with an edit (channel person,
      feedback F) while the classifier stub would now answer mockup-only. Assert no pt-classify
      dispatch, mock-data-author re-dispatched with F before any mockup-author dispatch.
  - name: test_pt_approve_resume_commits_paused_draft_without_redispatch
    location: unit_tests/test_plan_feature_pt_phase.py
    type: behavioral
    covers: [AC-4]
    description: |
      Resume with approve at pt-gate-mockdata: no mock-data-author dispatch; the commit stages
      exactly the recorded artifact paths, byte-identical to the paused draft.
  - name: test_unmatched_resume_answer_is_reported_not_dropped
    location: unit_tests/test_plan_feature_pt_phase.py
    type: behavioral
    covers: [AC-5]
    description: |
      Resume with a resume_answer for a gate other than the recorded one: status
      resume_answer_not_applied naming both gates, no PT author dispatched, pause record intact.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_pt_pause_context_carries_classification_and_stage_list | | |
| AC-2 | test_resume_does_not_reclassify_and_applies_mockdata_edit | | |
| AC-3 | test_resume_does_not_reclassify_and_applies_mockdata_edit | | |
| AC-4 | test_pt_approve_resume_commits_paused_draft_without_redispatch | | |
| AC-5 | test_unmatched_resume_answer_is_reported_not_dropped | | |
| AC-6 | `validate_product_truth.py` / classifier eval schema check | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] PT gate: pass a context holding the classifier decision, stage list, stage and reported
  artifact paths to `resolveGate`.
- [ ] PT phase start: on a resume, read the pause record once (reuse `peekPausedGateId`'s read
  or extend it to return the record). Take the classifier decision from it and skip the
  `pt-classifier` dispatch.
- [ ] PT loop: skip the author dispatch for the paused stage unless the answer is `edit`, the
  same way the AC loop does. On `approve`, commit the recorded paths.
- [ ] Unmatched `resume_answer`: halt with `resume_answer_not_applied` before any PT author
  dispatch.
- [ ] Add the eval row. Keep `plan-feature.js` shorter than at HEAD.

## Risk & Safety
- Touches money? No.
- Touches data? It changes what a resumed run commits to the product-truth store. The change
  narrows it to what the owner reviewed.
- Reversibility: revert the commit. Pause records written before the change carry no
  classifier decision. For those, the resume keeps today's behaviour (classify again) and logs
  that it had to.

## Out of Scope
- Making `pt-classifier` deterministic (model, temperature, prompt). This ticket removes the
  second classification from the resume path. Classifier accuracy is covered only by the eval row.
- The harness-level `resumeFromRunId` replay (KI-BO-20260907-resume-replays-cached-resolver), a
  different resume mechanism.
