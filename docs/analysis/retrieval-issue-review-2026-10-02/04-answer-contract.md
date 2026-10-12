---
title: 'Issue 04: Original-question and final-answer contract'
description: 'Historical analysis and saved observations for Issue 04: Original-question
  and final-answer contract.'
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# Issue 04: Original-question and final-answer contract

Analysis only; source pinned to `887c66d3896ba7727ce41b743887210a3883c6ce`. Scope: P0.4, RS-19/20/21/22/27. Read repository guidance and the research-agent, test-writer and BA prompts; apply their evidence, discrimination and single-owner principles, with the requested analysis artifact as the sole write. No providers, database writes, implementation or AC changes were performed. Source inspection and existing receipts are distinguished below; proposed tests have not been executed.

## Finding

The neutral retrieval layer already distinguishes an executed query from a fulfilled question. Its answer contract is not carried as a first-class contract through the research collector and final public bundle. Repair that seam before adding answer wording. Merely changing the Jev prompt, or marking every successful graph retrieval satisfied, would hide the defect.

### Observed evidence

- Fresh `reports/retrieval-scenarios-2026-10-02-retest-887c66d3/RS-02.live-response.json` and `RS-03.live-response.json` both contain `actual_response.status=waiting_human`, `output=null` and no evidence. They reached population clarification, not final assessment. Their actual questions say `population, population` and label category-prefixed text as the original question. RS-03 starts that alleged original with "The project's own stated rules, conventions and principles. Question:". These runs establish neither answer success nor a final-assessment failure. The earlier copied `human_prompts` wording in the new `live-boundary.json` summary has now been corrected from the fresh actual response packets; raw responses and historical receipts remain unchanged.
- The same directory's `active-controls.json` independently demonstrates lower-layer behavior: RQE-01-P returns the pinned 15-record population, 5 done/10 todo; RQE-01-N executes `ok` but answers `partial` with 15 missing work-status values and an unknown bucket; RQE-02-P returns the exact clause; RQE-02-N retains clipping as partial; RQE-06-N is unavailable/unresolved. These are explicit typed retrieval controls, not the ordinary question-to-answer journey.
- `continuation-controls.json` has three pages of five records. All answer assessments remain partial, including the final page, with no exact total. This is correct page honesty, not evidence of an accumulated 15-record answer. The artifact itself says `complete_journey=false`.

### Verified source causes and limits

1. **Original question changes identity before planning.** `kernel/capabilities/research/planning.py::_select_needs` (around 157) creates `EvidenceNeed.question` by prefixing the category description to `plan.question`. `integrations/query_growth.py::_initial` (44-70) then sets both `question` and `original_question` to that need question. `integrations/query_answer_planning.py::plan_answer` (62-102) derives requirements from it when no caller contract exists. A supplied `answer_requirements` survives, but the ordinary route does not retain an independently typed root question at this seam. Query hints carrying the goal are not an immutable original-question contract.
2. **Neutral answer guards are valuable and should be reused.** `knowledge/answer_models.py::AnswerRequirements`, `AnswerAssessment`; `knowledge/answers.py::assess_answer` (18), `_missing_fields` (99), `_limitations` (121) separately represent required fields, population, incomplete disclosure, source/generation and exact totals. `integrations/knowledge_execution.py::_kernel_result` (314) maps bounded evidence first, then `_assess_final_answer` (280) recalculates the answer; unavailable, clipping and unmet obligations affect the child result. Completeness of enumeration is deliberately distinct from completeness of required values: 15 known records may still have unknown work statuses.
3. **The answer packet stops at child diagnostics.** `_answer_diagnostics` (297) stores `result.answer` as JSON in `knowledge_answer`. The bundle instead uses `integrations/knowledge_assessment.py::assessment_bundle` (90), which returns `result.assessment`: the separate conditional interpretation/proof packet. `kernel/contracts/evidence.py::BundleBody` (234) and `research/state.py::Collected` (85) have conditional `assessments`, but no original requirements or typed answer assessment. `research/collect.py::_absorb_bundle` (78) consequently merges no `knowledge_answer`; `research/results.py::bundle_result` (92) does not return it. A saved child diagnostic is inspectable, but is not a consumer-visible root answer contract.
4. **Structured facts are also lost during mapping.** `integrations/knowledge_capability.py::to_kernel_evidence` (43) preserves source SHA, canonical locator and content, but does not carry `entity.properties`, `field_availability`, `field_locators` or `field_derivations`. Those are real disclosed facts from `knowledge/disclosure.py::evidence` (187). The exact criteria excerpt can survive; structured work-status values at their own field locators need not appear in that excerpt. Passing neutral sufficiency therefore does not prove that the final kernel evidence still exposes the values it assessed.
5. **Jev does not currently directly override a partial graph need.** `_kernel_result` always sets available nonempty graph coverage to `PARTIAL`, even when its neutral answer is fulfilled. `research/collect.py::_answer_checks` (198) only judges `SATISFIED` needs; `apply_answers` (277) only downgrades. `judge` (224) receives the root question for the broad `evaluable` question, but per-need checks use rewritten need text, and its state lacks required fields, population completeness and the answer packet. The literal semantic templates are already fixed; the missing invariant is their input target and obligations. A confident global evaluable vote cannot bypass current thin graph coverage. Conversely, no positive path here upgrades a fulfilled graph answer to satisfied.
6. **A mixed-source override remains a credible unexecuted failure mode.** `Collected.merge_coverage` (128) retains the strongest child coverage. A native satisfied sibling may overwrite graph partial for the same need; `research/assessments.py::guard_assessments` only guards conditional `result.assessment`, not missing original answer fields. A high per-need vote then has no deterministic original-field guard. This follows from the source paths; it is not a reproduced live incident. `bundle_result` bases execution completion only on unsatisfied required needs and `expected_coverage`; supporting-only or best-effort completion must not be advertised as original-question fulfillment.
7. **Existing synthesis is not the proposed optional wording contract.** `research/results.py::_synthesis_request` (25) sends a question and evidence IDs with two generic requirements. It sends no structured answer status or field/population limits. `host/synthesize.py::Synthesize` correctly labels output as host-reported inference. `research/executor.py::_collect` resumes a synthesized result directly to finish, without a new wording-acceptance stage. The target flow `retrieve-project-knowledge.flow.json` nodes `dispatch-wording`, `check-wording`, `judge-wording`, `respond` are declared design. `kernel/service_envelope.py::_visible_output` (144) already exposes validated partial root bundles; reuse that path. It does not reconstruct missing child answer diagnostics, and only a produced partial root output is visible, so a scheduler budget stop before that output is a separate end-to-end test obligation.

## Options and recommendation

| Option | Benefit | Cost / risk |
|---|---|---|
| Strengthen Jev wording alone | Small change | Cannot restore dropped facts, immutable question or completion evidence; reject as sufficient repair. |
| Extend existing typed research/bundle contracts and gates | Reuses neutral guards, LangGraph continuation, kernel output and host handoff; smallest complete seam repair | Requires compatible schema/model updates and every producer/consumer to be tested together. Recommended. |
| Add a separate answer composer and new orchestration graph | Can centralize all presentation policies | Creates another state/assessment owner and broadens scope before the existing seam is correct; defer. |

Stage 1: Preserve the original question and resolved `AnswerRequirements` once at the research boundary, separate from need/category and effective query wording. Carry a versioned/additive answer packet through retrieval, `Collected`, `ResearchContinuation`, root bundle and public output. Include disclosed values with per-field citation/availability, evidence identities, source SHA/generation, scope, missing fields, known versus exact totals, answer status and stop/continuation limits. Keep execution outcome and conditional proof assessment separate. Do not move the neutral package into the kernel dependency direction; adapt its validated packet at the existing integration boundary. Apply hard guards after the final disclosure/merge bounds, so no positive semantic vote can waive missing facts, wrong scope, clipping or incomplete enumeration.

Stage 2: Finish a structured answer through the existing research graph. Use one semantic assessment of the unchanged original question with the accepted answer packet; separate this from per-need relevance and comparison. A high vote permits fulfillment only when deterministic obligations pass. With no assessment budget, return the useful facts and an explicit unassessed/partial outcome. Do not turn an exact populated response into automatic semantic success, or an execution-completed run into answer fulfillment. Keep pages partial until a same-generation, same-scope aggregate proves unique complete coverage; a known subset is a valid useful return.

Stage 3: Add optional wording only after the structured path is proven. Preserve the structured answer if wording is unnecessary, unavailable or rejected. Reuse typed host handoff and existing source-reference validation; add explicit accepted-answer/limitations inputs and a bounded wording-acceptance state. Optional prose must not manufacture totals, erase unknowns or convert a declaration into execution proof.

Each node has exactly one owner; orchestration is not a second reasoning owner:

| Node / extension | Sole owner |
|---|---|
| Derive semantic answer requirements from original question | Jev |
| Validate, freeze and checkpoint requirements | System |
| Existing scoped retrieval and evidence mapping | System |
| Collect, deduplicate and validate actual facts/provenance/completeness | System |
| Judge original-question semantic adequacy over the checked packet | Jev |
| Apply non-waivable guards, route and assemble structured response | System |
| Decide whether a fulfilled answer needs prose | Jev |
| Construct/persist optional typed wording handoff | System |
| Author wording from accepted facts and limits | Host LLM |
| Validate matching wording output and references | System |
| Accept/revise/reject wording within limits | Jev |
| Final response assembly | System |

Existing human clarification remains the clarification issue's owner. No second planner, source reader, budget counter or retry loop is proposed here.

## AC disposition required before implementation

All named ACs currently have `req_status=active`, `readiness=approved`, `assigned_agent=python-coder`. Status below is verified `work_status`, not completion evidence. Paths are `docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/<ID>.yaml` unless noted.

| AC | Current status | Required treatment |
|---|---|---|
| KM-500c-2 | done | Reopen/reconcile original-question fulfillment at the actual root consumer. Amend with distinct execution/answer status, hard original-obligation gate and successful structured positive path. Existing tests prove bounded facets, not the missing end-to-end contract. |
| KM-500e-1 | in_progress | Complete immutable original question and required-field/population handoff through planning/resume/assessment; category text cannot replace it. Coordinate with clarification repair. |
| KM-500e-2 | in_progress | Complete field values, field citations and missing-field reasons through kernel mapping and root output, including exact full clauses after final clipping. |
| KM-500e-3 | in_progress | Complete root result for explicit 15/5/10 and alternate 11-leaf scope; require known-subset output on budget stop. Do not claim aggregation from three separately partial pages. |
| KM-500e-4 | in_progress | Preserve typed source/field/mapping/outage/limit causes in final answer; no query build to conceal a data gap. |
| KM-500g-1 / KM-500g-1-i | in_progress | Root observation must reference final answer fulfillment and missing fields, independent of trace delivery; child diagnostics alone are insufficient. |
| KM-500c-3 | done | Reuse bounded stopping; amend only for retained answer packet on exhaustion and any newly specified route. No claim that existing bounds prove changed-method behavior. |
| KM-500f-2 | in_progress | Preserve declared test references, supplied reports and inspected/executed proof as separate evidence classes; budget-limited proof inventory remains partial. |
| KM-500d-2 / KM-500g-2 | in_progress | RS-21: require branch/source/published-generation distinction in the final freshness answer; a manifest or graph record cannot establish current execution or deployment. |
| KM-500d-3 / KM-500a-4 | in_progress / todo | Consume independent question-only positive/negative receipts after the upstream blockers are fixed; do not close from scripted semantic votes. |

KM-400d-2 and KM-400d-4 are already `done` under KM-400-trustworthy-project-knowledge: reuse their provenance and bounds, do not duplicate them. Optional wording bypass plus validation/semantic acceptance needs an explicit subordinate contract under KM-500c-2 (new ID allocated by BA), rather than retroactively treating the existing synthesis transport as delivered wording behavior. This report changes no statuses.

## Required RED and end-to-end tests

Capture behavioral RED before implementation; import/schema errors are not evidence for these bugs. Pair every negative with a successful control through the same public route. Use serialized producer output, real KernelService/LangGraph/checkpoint consumers, controlled external actors, and a fresh-process resume where named. Assert root output, not only helper calls or child diagnostics.

1. **Identity and positive completion:** start with only the exact question and authorized context; let actual research planning produce category needs. Reopen and finish. Assert byte-exact original question, full canonical clause, source SHA/locator, root structured fulfilled answer; no optional host wording call. Mutant: derive original question from prefixed need; omit last And-clause; always return partial. Reuse both live question forms after their upstream routing is fixed.
2. **Missing fields despite optimistic Jev:** actual neutral producer returns `ok`, known population, missing `work_status`, with lifecycle `status=active`. Script every semantic answer high and include a satisfied native sibling for the same need. Assert missing-field identity/reason and unknown bucket reach root output, with no full breakdown or fulfillment. Positive twin supplies actual values. Mutants: strongest coverage wins globally; status replaces work_status; diagnostic exists but root packet disappears.
3. **Actual mapped facts/citations:** disclose work_status/level only as structured properties, with `/work_status` and `/level` locators and an unrelated criteria excerpt. Assert actual values and citations survive the real mapping/collector. Mutants: only excerpt/locator survives; silently reread an oracle to fill values; wrong generation accepted.
4. **Pagination and budget stop:** compare complete one-response 15/5/10 with three bounded pages, duplicates, unknown status, stale continuation and mid-run work/Jev/token exhaustion. Assert cumulative known unique records, source/scope and exact stop cause; exact total only after proven aggregate completeness. No additional retrieval after exhaustion. Include a stop before root finalize and require usable retained output, not just global evidence IDs.
5. **Optional wording:** satisfied structured facts bypass host and wording judgment. Host outage, unsupported citations, invented count, omitted missing-field qualifier and a stale resume must never replace the structured result or promote status. Bounded repair cannot reset budgets. Existing inference labels remain intact.
6. **RS-21/27 proof honesty:** declared covered_by paths, work_status=done and supplied historical report are never current-run execution proof. Combine a clipped clause, incomplete proof inventory, outdated generation and budget stop; return supported facts plus missing proof/freshness limits. Positive twin uses an attributable matching actual execution receipt. Test that declarations-only input cannot pass the execution claim.

`tests/knowledge/test_query_answer_contract_acceptance_kernel.py::test_scripted_sufficient_judgment_cannot_upgrade_unresolved_answer` currently checks a required graph need, root partial status and child diagnostics. Because graph coverage is always partial, it can pass without exercising a positive adequacy decision. Extend it with the mixed-source negative and positive completion twins above. Conditional-assessment tests in `test_query_answer_contract_acceptance_research_assessment.py` remain useful for `result.assessment`, not proof that `result.answer` reaches the root. A future live canary is an independently authorized evaluation step; none was run for this report.

## Cross-issue dependencies

Exact selection and clarification must first let the two real questions reach retrieval; this issue must not take over those repairs. Method-attempt work should reference this answer packet separately from execution status and conditional proof assessments; keep each attempt's scope/generation and final bounds. Traversal/aggregation supplies positive completeness evidence, while this issue owns how absent completeness constrains the answer. Proof-inventory discovery and source freshness supply facts to assess, not permission to infer them. Release evaluation owns the final unscripted receipts. The immediate deliverable is the single structured original-question answer seam, not the whole proposed retrieval portfolio.