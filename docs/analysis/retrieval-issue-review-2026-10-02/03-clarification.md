---
title: Focused count clarification and same-run resume
description: Source review and bounded repair proposal for RS-02 on merged main.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-02'
components: [knowledge_management, decision_kernel]
---

# Focused count clarification and same-run resume

Recommend repairing the existing answer-scope interaction, not adding a new planner: ask about unresolved meaning in ordinary language, interpret the reply against persisted bounded choices, validate the resulting patch, and resume the same research need. A wording-only change is insufficient because the current decoder treats a normal-language answer as component IDs.

This is analysis only at code `887c66d3896ba7727ce41b743887210a3883c6ce`. No runtime, tests, AC lifecycle or provider configuration was changed. Applicable research-agent, test-writer and business-analyst templates guided the source and proof review.

## Fresh observation and its limits

The actual [RS-02 response](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/RS-02.live-response.json) asks: **“How many ACs concern test writing? Exclude parent requirements.”** It now reaches `research` and `retrieve.repository`, then returns `waiting_human`, null output and no evidence. The run consumed three real Jev calls, resolved model `jev-1.13.0`, in 1.661 seconds. This is no longer the historical initial capability-routing wait.

Its pending question begins **“Please supply the missing population choices: population, population.”** It then requests JSON containing `scope`, lists internal enum names, and says whole-project enumeration is unsupported. The interaction offers no choices, advertises `free_text_allowed=true` and `structured_allowed=false`. Its subject is `need.task_context`; the displayed “Original question” is a derived need sentence containing the caller's question, not the exact caller text alone.

Clarification is justified: this question identifies neither a canonical family nor the meaning of “parent.” It does not ask for done/todo; adding work-status grouping would be an invented obligation. The separate approved “how many ... are done” example does require `work_status`. The observed defect is the unfocused, duplicated technical question and mismatched reply affordance, not an incorrect count: no count was returned. Jev's actual population confidence was 0.61 and inclusion confidence 0.50; uncertainty must not be fixed by lowering thresholds or silently choosing a family.

The served source is `59269e024e4d0290b68b03d0d382745966e67e29`, mapper 7, generation `20c370b99a39e0939e985846c9132986f8dc3052007b0dec5b43c19ddda7c28f`, semantic readiness false. The evaluator independently confirmed the retained oracle. These identify graph evidence availability, not the current code revision. Fifteen root-excluded descendants versus eleven terminal leaves belongs to the source-pinned TQ-500f example; “test writing” does not establish that family. No live human answer/resume was executed in this review.

The fresh [RS-03 response](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/RS-03.live-response.json) also receives population clarification despite being an exact-criterion question. That is an interface regression control for this repair; detailed exact-ID planning/catalog analysis belongs to the separate issue owner.

## Current source evidence

| Source / symbol | Verified behavior and implication |
|---|---|
| [query_answer_planning.py](../../../integrations/query_answer_planning.py), `plan_answer`, `_certain_choice` | Uses budgeted Jev over offered fields/populations/inclusion/levels; root candidates come only from literal IDs in the question. Existing non-null requirements bypass inference. It cannot establish TQ-500f from the vague phrase without further evidence or human input. |
| [query_answer_scope.py](../../../integrations/query_answer_scope.py), `missing_scope`, `scope_clarification` | Concatenates planning-missing and scope-missing lists without deduplication. Unknown population yields only `population`, hiding subsequent root/level/inclusion needs until later. Fixed text always discusses inclusion and JSON, even when that is not the unresolved fact. |
| [query_planning.py](../../../integrations/query_planning.py), `human_scope` | Only text starting with `{` invokes `merge_scope` for `answer_scope`. Ordinary text otherwise becomes `component_ids`; `choice_id` is not decoded. This source-proven dispatch defect can reject the reply or leave obligations unresolved. A complete public ordinary-language reproduction is still required. |
| [query_answer_scope.py](../../../integrations/query_answer_scope.py), `merge_scope` | Preserves original obligations and appends required fields; rejects replacement of established choices. Unknown population stays unknown. Reuse this validation boundary, not a freeform overwrite of requirements. |
| [query_growth.py](../../../integrations/query_growth.py), `_initial`, `_resume`, `_continued` | Pins source before pause, persists question/need/requirements, and accepts exactly one completed current-wait child of the expected schema. Preserve these controls and same-run ownership. |
| [query_graph.py](../../../integrations/query_graph.py), `_resumed`, `_clarify_scope` | Existing LangGraph resume returns through scope checking. An unresolved plain-text reply can therefore lead to another scope question; this consequence is inferred from the connected path, not claimed as a live resumed observation. |
| [payloads.py](../../../kernel/contracts/payloads.py), `HumanQuestionRequestPayload`, `HumanAnswerPayload` | Existing choices and free-text answers suffice for this interaction. The structured-answer branch is approval/criteria editing, not arbitrary scope JSON; merely enabling `structured_allowed` does not repair the contract. |
| [kernel_config.default.json](../../../config/kernel_config.default.json), `intent.max_clarifications` | Default is **two**, shared with query clarification. Asking population, root, levels and inclusion one at a time can exhaust the budget. Do not silently raise/reset it. |

Existing [public acceptance tests](../../../tests/knowledge/test_query_answer_contract_acceptance_kernel.py) check an ambiguous question, explicit scope bypass and persisted continuation. Their fresh-process answer supplies JSON inside `free_text`; their prompt assertion expects enum names. They establish useful transport guarantees but do not prove an ordinary-language reply is consumed correctly. No old test pass is presented as new live quality evidence.

## Options and recommendation

| Option | Benefit | Limitation |
|---|---|---|
| Deduplicate and rewrite the current JSON prompt only | Smallest text change; preserves machine clients | Leaves ordinary-language decoding broken and later scope questions repetitive. Insufficient. |
| **Persist a focused question contract; support choices and bounded interpretation of prose** | Reuses human interaction, Jev, LangGraph and durable state; fixes the actual handoff | Requires explicit choice-to-patch state and semantic interpretation tests. Recommended. |
| Delegate arbitrary reply rewriting to an LLM host operation | Could support broad freeform preparation | Unnecessary generation/host schema work for these bounded meanings; risks inventing IDs and expands this issue. Defer. |

Recommended sequence, each action with one owner:

1. **System:** derive a unique unresolved-slot set from existing obligations; persist a question descriptor with offered meanings, source/need identity and already-resolved values. Keep exact caller question separately from the derived research need. Require population clarification only for obligations that need population completeness; a single-record quotation must not inherit it.
2. **System:** render one focused prompt covering material unknowns within the remaining clarification budget. For the vague RS-02 case: “Do you mean a particular requirements family, or all test-writing ACs in the project? If a family, which one? By excluding parents, do you mean only its top requirement or every requirement that has children?” Do not demand a source SHA or internal field names. Already explicit choices must disappear from the prompt.
3. **Human:** answer using choices or ordinary language. Useful ordinary reply: “The TQ-500f family, L2 and L3, excluding only TQ-500f.” This is a user choice, not a mapping inferred from the original vague phrase.
4. **System:** map a submitted offered choice deterministically, preserve the reply and extract literal candidate IDs without treating arbitrary words as component IDs. For prose needing interpretation, construct a bounded Jev request using the pending question and permitted candidate meanings.
5. **Jev:** select only supplied interpretations or unresolved; never author IDs, query syntax or a replacement original question. No judgment call is necessary for a valid unambiguous offered choice. Ambiguous/conflicting prose remains unresolved.
6. **System:** validate the patch against established fields, authorization and source identity, then apply `merge_scope`. Resume the existing graph and original need; only remaining material unknowns may cause another question. Invalid/no-progress/exhausted replies produce an explicit bounded unresolved result, with history retained.

Use the existing `clarify_scope -> waiting -> resume` lifecycle. If semantic reply interpretation needs an additional node, make it an explicit node in this existing StateGraph and use `ask_jev` with the current budget; do not hide a parallel orchestration loop in a parser. Persist the question descriptor in the existing continuation, not a second store.

Whole-project scope is a meaningful user choice even though the current population model cannot enumerate it. Preserve that intention and explain the unsupported capability; offer a narrower family only as an explicit alternative. Never coerce it to `returned_entities` or `ac_descendants`. The smallest repair need not implement project-wide enumeration. A topical family name without a verified ID needs discovery or clarification, not a fabricated canonical ID.

## Acceptance mapping and scope

All statuses below were read from current canonical YAML; none is changed here. Files reside under [KM-500 research capability growth](../../acceptance-criteria/knowledge-management/KM-500-research-capability-growth/).

| AC | Readiness / work status | Application |
|---|---|---|
| KM-500a-1 | approved / done | Focused missing inputs, no execution before resolution, same need resumes, no repeat for sufficient input. Existing authority for a regression repair; done status is not evidence that this newly observed prose path works. |
| KM-500a-2 | approved / done | Validated arguments and original scope/budget; preserve explicit typed low-level selection compatibility. |
| KM-500c-2 | approved / done | Evidence/answer sufficiency and limitations remain separate from query success. |
| KM-500c-3 | approved / done | No unchanged infinite continuation or budget reset; explicit unresolved result. |
| KM-500e-1 | approved / in_progress | Direct count/population/root-versus-parent/explicit-bypass/original-obligation contract. Primary scope for this repair. |
| KM-500e-2 | approved / in_progress | Preserve requested field meanings; lifecycle status cannot replace work status. |
| KM-500e-3 | approved / in_progress | Source-specific membership/count completeness; no family-as-project or page-as-total claims. |
| KM-500a-4 | approved / todo | Real-provider planning-quality proof remains separate from scripted tests. |

The bounded repair fits existing approved requirements. No new AC or lifecycle project is needed for it. A universal ordinary-language grammar, whole-project topical enumeration or automatic canonical-family discovery would require additional design scope; do not smuggle them into this fix. Product choice still needed only if project-wide counting itself is to be delivered rather than honestly reported unsupported.

## Proposed RED and acceptance proof

Use public `KernelService.start_run/resume_run` with actual checkpoint storage and controlled external Jev responses. Assert the actual question, child dispatch and consumer result, not helper existence. Keep controlled tests distinct from the fresh live receipt above.

- **RS-02 question-only RED:** no caller-built requirements; wait names family/project and inclusion meaning once, no JSON obligation or repeated labels, no implicit TQ-500f and no graph count/build while unresolved. Do not require `work_status` for a question that only asks quantity; paired “how many are done?” must require it.
- **Ordinary-language continuation RED:** answer the pending question with the explicit family/levels/root-only sentence; reopen the service in a fresh process and resume the same run. Assert original caller question, need ID, source/generation, permissions, retained fields and accumulated budgets; execute only after accepted requirements and do not repeat resolved questions.
- **Choice and ambiguity controls:** valid offered choice avoids an unnecessary interpretation call; unknown choice, conflicting prose, empty reply and provider failure remain unresolved. Ensure a prose reply never becomes component IDs. Duplicate/stale/wrong-interaction submissions cannot advance a different wait or repeat execution.
- **Explicit bypass:** the fully specified natural-language L2/L3 root-only question gets no redundant scope prompt; a supplied complete typed answer contract remains compatible. This is clarification bypass, not removal of semantic method selection.
- **Population controls:** root-only versus all-parent exclusion produces different membership on an independently built source fixture; whole-project intent stays explicit unsupported; unrelated family/revision does not reuse the TQ oracle. Budget-limited evidence never gains an exact total.
- **Boundary with exact-ID issue:** a single known-AC criterion request must not ask family/levels/count inclusion. Preserve exact-ID interpretation and query-catalog work as a separate dependency, with a shared regression test at answer-contract production.
- **Budget/no-progress:** default two-clarification limit remains effective. Group related unresolved choices or terminate honestly; never reset the counter after reopening. Required-field uncertainty must have a reachable answer path without erasing established fields.

Discriminating mutants should restore the current generic free-text-to-component branch, drop stored obligations, default a missing root, re-ask resolved inclusion, or reset the clarification counter. Each must fail a behavioral assertion. No new paid evaluation or runtime tests were executed by this analyst.

## Delivery boundary

Dependencies are the current typed research binding (already in this base), the exact-ID/answer-obligation analyst for non-count gating, and source capability checks for unavailable project-wide scope. The clarification repair can be implemented and proven with existing local graph fixtures without waiting for a new search/traversal/learning design. A future authorized live continuation is needed to establish natural-language quality; this review does not invent a human answer or claim the saved live wait was resumed.
