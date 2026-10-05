---
title: Natural-language exact-ID retrieval review
description: Current-code diagnosis and staged repair options for P0.2 and RS-03, without runtime or acceptance-status changes.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-02'
components: [knowledge_management, decision_kernel]
---

# P0.2 / RS-03: make a literal AC ID executable through ordinary research

**Finding:** The fresh RS-03 live run at `887c66d3896ba7727ce41b743887210a3883c6ce` now reaches research but stops at an inappropriate count-population clarification before query selection. Behind that observed blocker, the planner still excludes exact lookup, fixes execution to graph mode, and treats entity IDs as component IDs. Repair the exact-question obligation first, then these three seams together; readiness must also accept a known entity without requiring a component or population root.

The public acceptance question remains **“For KM-500c-2, what must tests demonstrate?”** The caller supplies that question and may supply literal IDs or keywords. The caller must not supply `get_entities`, an internal population enum, a fabricated component, or answer requirements as a workaround. Host-owned repository, permissions, source policy and budgets remain authoritative.

## Evidence boundary

- Source inspection is pinned to `887c66d3896ba7727ce41b743887210a3883c6ce`, confirmed by the independent evaluator. No production files, tests, ACs or statuses were changed by this review; this report is its only write. I made no database or provider calls.
- The [fresh readiness receipt](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/readiness.json), observed at `2026-10-02T17:51:17.321971+00:00`, reports repository `leafcutter`, source SHA `59269e024e4d0290b68b03d0d382745966e67e29`, generation `20c370b99a39e0939e985846c9132986f8dc3052007b0dec5b43c19ddda7c28f`, mapper `7`, semantic readiness `false`. The manifest maps `AcceptanceCriterion` and its `criteria` field. Running current code against this generation does not mean the generation contains current-main source.
- The [fresh RS-03 input](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/requests/RS-03.live.json) is the unchanged question in `leafcutter.research_request.v1`, empty `component_ids`, `read_repo`, and a host-pinned published revision. It does not supply an operation or answer contract.
- The [completion gap analysis](../2026-10-02-retrieval-completion-gap-analysis.md) and [scenario catalog](../2026-10-02-retrieval-scenarios.md) were treated as leads. Their earlier live stop at ability routing is historical evidence, not the result of the present retest.
- Repository `.claude/CLAUDE.md`, the research-agent reference, and test-writer, BA and IT-PO templates guided source gathering, behavioral boundaries and test angles. Their ticket/signoff/AC-mutation workflows were not invoked.

## Fresh live result: exact target recognized, irrelevant population still blocks

The [actual RS-03 receipt](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/RS-03.live-response.json) records `waiting_human`, no output or answer, model `jev-1.13.0`, five Jev calls and 2.267 seconds. Real research and two registered `retrieve.repository` invocations ran. Five calls comprise one `research.plan_needs` call plus two answer-contract invocations, each split into two provider chunks; this is not population being asked twice within one child.

In those two invocations, the literal `KM-500c-2` choice was confident (probability/confidence `.92/.83` and `.94/.88`). Population was `clarify` at `.52/.35`, then `returned_entities` at `.55/.39`. Both fail `query_answer_planning.py::_certain_choice` lines 55–58. `plan_answer` lines 97–100 sets population to `None` and adds `answer_planning_missing=["population"]`. `query_graph.py::_clarify_scope` stops before readiness or selection; `query_answer_scope.py::scope_clarification` line 55 concatenates that field with `missing_scope`'s same field, producing “population, population” and a JSON/count prompt. The visible wait names `need.internal_principles` and embeds a category-prefixed original question.

**Observed immediate blocker:** a source-criterion question is forced through uncertain count-population planning even though its literal target is recognized. The downstream catalog, mode and binding defects are independently source-proven, but this live run did not execute them. The trial does not prove why Jev was uncertain or justify lowering thresholds. The exact slice needs a bounded semantic distinction between facts for explicit entities and a requested hierarchy/count, followed by only the applicable scope obligations; coordinate its wording/resume behavior with P0.3.

## Current path and observed source facts

| Boundary | Exact current anchor | What the code establishes |
|---|---|---|
| Typed question reaches research | `tests/kernel/intent/test_typed_research_binding.py::test_original_questions_reach_research_without_claiming_answer_completion` | The merged regression explicitly proves reaching `research.plan_needs`, not successful exact selection or answering RS-03. Other tests preserve permission, ambiguity and unsupported-pair gates. |
| Research creates retrieval children | `kernel/capabilities/research/planning.py::_select_needs` lines 164–166; `_child` lines 213–247 | A category-prefixed `need.question` is generated; the retrieval payload carries answer requirements when supplied, but has no separate executable literal-ID field. Original-question preservation is a cross-issue dependency. |
| Production query-planner entry | `integrations/knowledge_capability.py::KnowledgeRetrievalExecutor.ainvoke` lines 206–225 | With catalog/admission configured and no explicit `knowledge` request, the real facade calls `invoke_query_growth`. A direct typed exact test bypasses this selection path. |
| Exact operation is registered | `knowledge/contracts.py::OPERATIONS` line 98; `KnowledgeRetrievalRequest.registered_arguments` lines 168–176 | `get_entities` requires `entity_ids` and only mode `exact`; mismatched graph mode is rejected. |
| Catalog already describes exact | `knowledge/query_catalog.py::BUILTIN_PURPOSES` line 103; `builtin_descriptors` lines 127–160 | Exact lookup has purpose, typed input, version/digest, result meaning and `modes=["exact"]`. A new query implementation is unnecessary. |
| Planner filters it out | `integrations/query_growth.py::_select` lines 86–97 | Only descriptors whose modes contain `graph` are offered. `get_entities` cannot be a valid Jev choice. `integrations/query_planning.py::choose` lines 35–40 correctly refuses an unoffered choice. |
| Literal IDs become roots only | `integrations/query_answer_planning.py::plan_answer` lines 75–100 | A bounded regex extracts caller text candidates for the `root` population choice. It does not populate executable `entity_ids`. Fresh live choices establish that recognizing the ID alone does not get past population planning. |
| Readiness presumes components/roots | `integrations/query_growth.py::_ready` lines 311–317 | Even a Jev `ready` choice causes clarification when both `component_ids` and `answer_requirements.scope.root_id` are empty. An exact target should not depend on a selected hierarchy root. |
| Binding confuses ID roles | `integrations/query_growth.py::_arguments` lines 126–143 | Both `entity_ids` and `component_ids` are filled from `state["component_ids"]`; every string-list argument must be a subset of that list. A literal `KM-500c-2` seed is rejected unless improperly masquerading as a component. |
| Required-empty values are not “missing” here | `integrations/query_growth.py::_execute` lines 165–170 | The missing-input check tests key presence, not a required nonempty list. Binding an empty `entity_ids` therefore advances to neutral validation, which rejects it. This is an inferred downstream outcome from the inspected guards. |
| Execution fixes wrong mode | `integrations/query_growth.py::_execute` lines 171–178 | All chosen descriptors become a request with `mode="graph"`. Adding exact to the menu alone would still fail request validation. |
| Clarification repeats the conflation | `integrations/query_planning.py::clarification` lines 76–94; `human_scope` lines 179–187 | Entity/component inputs are excluded from generic missing-parameter prompts; no components means “Which project component…”. Every normal clarification runs `_validate_components`, requiring at least one component. An entity-input answer needs its own typed role. |
| Exact service and source checks exist | `knowledge/adapters/neo4j_queries.py::query` exact branch lines 61–79; `integrations/knowledge_execution.py::_scoped_request`, `_request`, `_authorized`, `_kernel_result` | Exact query is parameterized by repository/generation and canonical IDs. Trusted repository/revision, authorized source/read roots, response identity and bounded disclosure remain existing enforcement points. |
| Missing IDs/clauses remain unresolved | `knowledge/answers.py::assess_answer`, `_hard_failure`, `_limitations` lines 154–156 | Exact missing requested IDs, unavailable execution, absent source identity and truncated required criteria cannot be waived into a fulfilled answer. Missing exact lookup can remain service `ok` with empty evidence while the question is unresolved. |

### An attractive shortcut that would fail RS-03

`integrations/retrieval_decision.py::choose_retrieval_mode` lines 57–72 already accepts `known_ids`, but routes any known-ID question containing `test`, `verify` or `coverage` to `get_related_tests`. The exact RS-03 wording contains “tests” while asking for the AC's governing criterion. Merely passing extracted IDs into this helper would therefore select the wrong evidence path. Its current caller, `integrations/knowledge_execution.py::_request` lines 150–153, passes `known_ids=[]`; the configured catalog path is different again.

This is a source-proven routing rule and a predictable wrong outcome for that proposed shortcut, not a claim that the current live run executed this helper. Reuse the neutral service and guarded execution; do not reuse that keyword rule as natural-language intent resolution.

## Diagnosis: observed versus inferred

**Observed in code:** exact is omitted from the offered catalog; graph mode is forced; entity lists are populated and constrained as component lists; literal candidates are only population roots; known entity targets cannot independently satisfy readiness; clarification has the same component presumption. The persisted query graph currently has `load → plan_answer → clarify_scope → readiness → target → capability_fit → select → execute → END`, with existing continuation branches (`integrations/query_graph.py::build_query_growth_graph`, lines 190–210).

**Inferred cause:** query growth was extended around component-seeded graph recipes, and those assumptions persisted in the general research planner. A transport feature (`get_entities`) was never wired as an ordinary natural-language method with its own argument role and execution mode. This is not evidence that exact data is absent, that the current graph needs republishing to repair selection, or that lowering a confidence threshold would fix it.

**Scope of the claim:** we can prove the selection/binding mismatch without claiming every live failure has that immediate cause. Any earlier answer-contract, readiness or target-kind wait must be reported at its actual stage. A live run that stops before query selection does not dynamically prove the subsequent exact execution defect.

## Repair options and tradeoffs

| Option | Implementation shape | Benefits | Costs / boundaries |
|---|---|---|---|
| **A. Extend the existing registered-query graph (recommended)** | Offer supported exact and graph contracts; bind separately typed literal entity candidates; derive mode from selected descriptor; keep Jev semantic choice and existing neutral execution. | Smallest coherent repair; one existing registry/facade/checkpoint/validation path; preserves distinction between an AC clause request and linked-test request. | Requires touching catalog eligibility, input role, readiness and execution together. Broad semantic search remains outside this slice. |
| B. Add an explicit exact branch to the same retrieval graph | Jev makes a bounded exact-versus-relationship choice; System uses the existing exact neutral request; other needs continue through existing query selection. | Exact branch can avoid graph-specific preparation; direct source obligations are simple to inspect. | Creates an additional semantic gate and branch to maintain; catalog metadata can drift unless both paths use it. A literal-ID regex alone cannot own this choice. |
| C. Introduce a uniform query binding contract first | Extend descriptors with supported modes, input roles/seed kinds and a generic typed binding result for all operations, then integrate exact. | Scales to optional argument preparation, graph seeds and later methods; avoids repeated ID-role bugs. | Larger change and migration/test surface than RS-03 requires. It must not turn into a broad planning workflow or delay one exact answer behind optional generation. |

Option A should introduce only the binding fields needed for exact and preserve existing graph descriptors. A later shared argument contract can absorb those fields. Keeping only the privileged explicit `knowledge.operation` path working is useful backward compatibility, but does not satisfy this issue.

## Smallest staged repair, with explicit LangGraph owners

Each row names one owner. Proposed nodes are additions/splits to the existing query graph, not a second orchestrator. Kernel remains the owner of durable waits, authority and cumulative budgets.

| Node / change | Sole owner | Contract and behavior |
|---|---|---|
| Existing `load` | System | Reuse `_initial`, trusted repository/source pinning and continuation. Carry the original question separately from a generated need label. Preserve known literal IDs as data, never authority or operation names. |
| New `bind_known_targets` | System | Extract bounded literal ID candidates from the original caller question and merge optional explicit IDs with origin metadata; preserve exact spelling, do not replace one ID with a similar AC, and keep `entity_ids` separate from `component_ids`. Extraction proves literal occurrence, not existence, kind or relevance. |
| Existing `plan_answer` | Jev | Choose required facts and bounded question meaning from the original question: facts about explicit entities versus hierarchy/count. Apply population/inclusion/levels only when that meaning requires them. For RS-03 the required governing clause is `criteria`; do not require a family root, parent-inclusion choice or caller-supplied answer requirements. |
| Existing `readiness` | Jev | Judge remaining meaning using the actual known-target context. System must remove the unconditional “no component/no root” fallback for a validated known entity target. Missing literal target and ambiguous target roles remain distinct bounded choices. |
| Existing `target` split to `choose_target_kind` | Jev | Choose the requested result kind from offered meanings; “what must tests demonstrate?” can ask for an `AcceptanceCriterion`, whereas “which tests cover this AC?” asks for `Test`. Do not infer this from the substring “test”. |
| Existing `capability_fit` / new `validate_target_kind` | System | Validate the choice against actual pinned manifest support and available fields. Do not treat a field/source gap as a missing-query opportunity. Exact output kind must satisfy accepted semantics or be explicitly unresolved. |
| New `offer_queries` | System | Filter descriptors against supported execution modes/source readiness and retain stable operation/version/digest plus input/result contract. Include exact `get_entities` where available. Do not silently add semantic operations merely because the graph-only filter is being removed. |
| Existing `select` | Jev | Choose only one offered descriptor, clarification or stop for this slice. Preserve selection reason. Known IDs provide inputs; they do not mandate exact when the question asks for a relationship. |
| New `bind_query_inputs` | System | Bind the selected contract's entity arguments from accepted entity targets and component arguments from established components. Derive one allowed execution mode from the descriptor/validated selection. Validate nonempty required values, limits, origins and scope before backend access; do not infer entity authorization from ID shape. |
| Existing `clarify` / `resume` | System | Dispatch the existing human wait and consume only its matching response; ask only for genuinely missing target/meaning. Entity replies must not be decoded as component IDs. Preserve selected descriptor, question, source identity, prior facts and consumed budget. Human supplies missing intent; no new LLM path is required. |
| Existing `execute` | System | Reuse `QueryCatalog.request → invoke_knowledge → KnowledgeService.retrieve`, source/response authorization, disclosure limits, answer assessment and diagnostics. Dispatch accepted exact request once; prohibit substituted IDs, incompatible mode and foreign source before exposure. |
| Existing research assessment | Jev | Judge original-question usefulness using retrieved, source-bound clauses. System's existing missing-ID, missing-field, truncation and authority checks remain non-waivable. Final structured return is coordinated with P0.4. |

For the unchanged simple RS-03 path, there should be no argument-generation or query-build host handoff. If later ambiguous freeform input interpretation genuinely needs an LLM, use a new typed operation in the existing kernel host packet/submit/resume mechanism, bounded and validated before Jev acceptance. Neither a direct SDK call in these nodes nor a generic unregistered fallback is part of this repair.

Recommended delivery stages:

1. **Write the discriminating failing seam tests.** Start with the fresh non-count exact question being stopped by population planning. Use real `KernelService`, descriptor producer, query graph, request validator, neutral service and final output consumer. Control only Jev judgments and storage/source fixtures; capture the pre-fix failures at actual gates.
2. **Repair applicable obligations, mode and ID roles as one slice.** Jev distinguishes explicit-entity facts from hierarchy/count; System checks only applicable missing inputs. Separate literal targets from components, offer exact, allow target-ready exact requests, derive/validate mode, and retain source/permission/budget checks. Optional public IDs should be an additive typed field propagated through `ResearchRequestPayload → Plan → RetrievalRequestPayload`; question-only operation must still work. Do not overload `Scope.component_ids`, `explicit_locators` or `knowledge.operation`.
3. **Close the original public answer and run the real canary.** Join P0.4's structured fact/answer return; rerun the exact unchanged question and negative controls at a frozen source, recording real Jev selection separately from scripted mechanism proof. No status becomes done from a descriptor-only unit test.

## Existing AC ownership and exact gaps

Statuses below are read from the YAML at the pinned code SHA, not changed or inferred from this report.

| Existing AC | `work_status` | Applicable obligation and remaining evidence |
|---|---|---|
| **KM-400a-2 — Known IDs return exact attributable matches** | `done` | Exact registered operation must preserve alpha's ID/revision/locator, return absent ID as empty, never substitute a similar entity, and make no semantic/LLM call inside that operation. Preserve this neutral behavior. It is not proof of natural-language query selection. |
| **KM-500a-2 — Select a registered query from its purpose and input contract** | `done` | Candidate metadata, bounded semantic selection, missing-input clarification and validated original-scope execution own the natural-language wiring repair. Current test specification explicitly says “catalog-driven graph query choice”; add exact-mode and literal-ID seam coverage instead of claiming existing done proves it. Existing explicit operation bypass remains a separate allowed path. |
| **KM-500a-1 — Ask only for missing research inputs and continue from the answer** | `done` | Known exact target must not trigger a component workaround; an actually missing/ambiguous ID needs focused clarification and same-run resume. Extend coverage to entity-role clarification without changing historical completion claims. |
| **KM-500e-2 — Return canonical fields and clauses without changing their meaning** | `in_progress` | Required canonical criterion, identity, revision and locator must survive disclosure and final output; missing/truncated clauses stay unresolved. This is the exact answer payload obligation. |
| **KM-500c-2 — Judge the original question against the evidence actually retrieved** | `done` | Existing sufficiency and separation of execution/build/answer outcomes constrain the fix. In RS-03 this is also the requested source entity; its done status says nothing about whether the runtime retrieved its clause. Do not substitute another similarly worded AC. |
| **KM-500d-1 — Let agents discover and use the right knowledge entry point** | `in_progress` | Public question-only route and downstream use must be demonstrated together. Typed root binding alone is partial proof. |
| **KM-500e-1 — Resolve the facts and scope needed to answer the original question** | `in_progress` | Preserve original question and distinguish exact entity targets from hierarchy roots; relevant upstream input to this repair. |
| **KM-500a-4 — Measure real planning and selection quality before claiming readiness** | `todo` | A scripted exact-choice test proves execution plumbing, not Jev semantic quality. Actual original-question run, target/query choices, stages and honest failures are required for the live claim. |

No replacement AC is proposed. Any extension of the natural-language selection coverage belongs to these existing obligations; optional general argument-generation belongs to its separately reviewed issue.

## Meaningful RED, negative and end-to-end acceptance tests

These are proposed tests, not tests executed by this analyst. “Expected RED” means a specific current defect should produce failure, not a captured run receipt. Follow the test-writer template's reachability/seam/discrimination requirements and record actual pre-fix failure output before implementation.

| Test | Required observable assertions | Plausible wrong version caught |
|---|---|---|
| **Question-only RS-03 through actual kernel** — expected RED | Input contains question only, host scope and `read_repo`; no operation/requirements/components. With fixed Jev semantic choices, actual offered catalog includes exact, selected `get_entities` binds only `KM-500c-2`, request mode is `exact`, real neutral service returns canonical criterion and locator, and public output keeps that evidence. | Current graph-only menu; menu-only fix with graph mode; entity list copied from components; helper merely exists but public producer never reaches it. |
| **Exact facts do not require count scope** — expected RED | Replay the captured population uncertainty with a bounded explicit-entity fact interpretation and known literal target. No parent-inclusion/count JSON prompt is emitted; a genuinely ambiguous count control still clarifies. | Blanket removal of clarification, global threshold lowering, or an exact happy path that only works with supplied internal population values. |
| **Readiness without artificial population root** — expected RED | Same target with `returned_entities`, no `root_id`, no component is ready. Do not emit a component question or build request. Literal target context is produced by the real input parser. | Accidental success only because scripted Jev puts an exact AC into `scope.root_id`. |
| **Exact clause versus linked tests** — discrimination | Pair “For KM-500c-2, what must tests demonstrate?” with “Which tests cover KM-500c-2?”. Keep same literal ID and source; first returns governing AC criterion, second can select the offered test relation. Record distinct Jev choices/operations. | Keyword rule that maps every “tests” question to `get_related_tests`, or every known ID to exact. |
| **Mixed roles and optional IDs** — expected RED | Component `knowledge_management` plus literal target `KM-500c-2` must bind the AC for exact; multiple literal IDs remain bounded and deduplicated; optional explicit IDs propagate through real producer/consumer fields. A conflicting/ambiguous target needs a focused question. | Requiring `entity_ids ⊆ component_ids`, taking first component as entity, or newly added IDs field dropped by child construction. |
| **Absent exact ID / similar neighbor** | Absent ID with a similarly named present AC returns no substitute. Neutral status may be `ok`/empty; answer is unresolved for requested clauses. No semantic/LLM calls inside exact operation and no build request caused merely by absence. | Semantic fallback silently replacing the requested AC; empty success labeled answered. |
| **Wrong kind and foreign source** | Accepted `AcceptanceCriterion` obligation with same literal ID mapped to a different kind cannot fulfill it. Separate alpha/beta repositories sharing an ID, wrong revision, denied path and tampered response/request identity must not expose foreign evidence. | Treating any canonical ID match as sufficient; accepting source labels without actual scope validation. |
| **Mode/input tampering before backend** | Unoffered operation, incompatible mode, unbound ID, empty/malformed/over-limit ID list and unregistered executable query text are rejected before backend calls. | Merely trusting a Jev-selected dict, menu-only fix, or checking only argument-key presence. |
| **Disclosure and budget boundaries** | Clipped/omitted criterion, one-of-many IDs clipped by cap, unavailable backend and cumulative budget exhaustion retain attributable partial/unresolved outcomes. No source byte is reconstructed by a model. | Removing existing answer checks to make the happy path green; resetting limits on exact selection. |
| **Clarification continuation** | If target role really is ambiguous, matching human response resumes same question/source/descriptor and consumed budget; stale/foreign/duplicate replies cannot execute another exact request or broaden permission. | Entity answer parsed as component scope; fresh retry discards source pin or spends again. |
| **Real-provider canary** | Independent evaluator repeats the literal RS-03 question at pinned code/config/source; captures actual stages, model/version, bounded choice receipts, operation/mode/arguments, source identity, clause locator, status and cost/calls. No scripted exact selection or supplied answer contract counts as this test. | Local mechanism pass presented as live semantic success, or code SHA confused with serving source SHA. |

Existing tests worth retaining: `tests/knowledge/test_core.py` exact identity, invalid modes/arguments, foreign candidates, stale source, disclosure and cumulative bounds; `tests/knowledge/test_kernel_bridge.py` response binding and clipping; `tests/kernel/intent/test_typed_research_binding.py` real root eligibility; `tests/knowledge/test_query_growth_kernel.py` governed selection/build/resume. Their current direct-operation or graph fixtures do not prove RS-03's complete natural-language journey.

## Interfaces and dependencies sent to coordination

- **P0.1 route:** merged typed binding supplies reachability for a validated research pair; independent live retest determines the actual next stop. Do not lower routing confidence as the exact-ID fix.
- **P0.3 clarification:** share the input-role distinction, focused missing-target prompt and existing resume envelope. Known exact ID must not force component/population clarification. This report does not redesign the count clarification flow.
- **P0.4 answer return:** preserve a separate original question and return the actual exact clause, field availability, source identity and locator. Successful exact execution is necessary but not the completed public answer.
- **S2 optional preparation:** any future typed candidate arguments can reuse the same role-aware validator. Neither generation nor five-term preparation is a dependency of simple exact lookup.
- **S1 attempts / S5 assessment:** record selected descriptor/mode/bound IDs and actual result in their eventual shared attempt contract; do not build a method portfolio for this narrow repair. One exact attempt cannot claim comparative superiority over untried methods.
- **S9 source freshness:** continue exposing the revision actually used. Publication is not required to fix planner wiring, but is required before claiming answers describe newer source bytes.
