---
title: Retrieval scenario execution map
description: Independent oracle and public-route feasibility map for the 29 proposed retrieval scenarios.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-02'
components: [knowledge_management, decision_kernel]
---
# Execution map for the 29 retrieval scenarios

This is a read-only test-planning companion to the [saved scenarios](2026-10-02-retrieval-scenarios.md). Use each `RS` case's **verbatim caller question** and fixture; do not rewrite the question to make an existing operation pass. An existing typed request may test a narrower fact, but it does not prove that the question-only target journey selected the right method. This map was prepared independently of new run outputs. It makes no claim that a case was executed.

The baseline entry points are the [standalone retrieval CLI](../how-to/run-knowledge-retrieval.md), `python -m knowledge evaluate` using the [reviewed twelve-case pack](2026-10-01-repository-query-evaluation-runnable.json), the [kernel research run/resume route](../how-to/kernel-query-growth.md) with explicitly controlled Jev/host/human actors, and the optional `knowledge assess` consumer for supplied evidence. A real Jev call or provider-backed search requires separate authorization and must be labeled as such. The target [main flow](../product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json) and children are draft/spec, while [current baseline](../product-truth/flows/leafcutter/retrieval-current-baseline.flow.json) describes built routes. No `RS` case is a full target-flow pass merely because a baseline unit or direct operation works.

## Verdict vocabulary

- **Public answer slice:** today’s public CLI/kernel can return an actual bounded answer or honest refusal for the original fact, with typed operation and/or controlled Jev explicitly labeled. This is a partial scenario observation, not a full target journey pass.
- **Public control slice:** a public route can exercise a deliberate missing-field, partial, unavailable or query-fitness control; any answer quality remains limited by its setup.
- **Lower layer:** a current deterministic service/test can test an invariant, but not the required question-level routing.
- **Target absent:** the scenario's decisive method/transition does not exist on the current route. Record `unsupported/not_run`, not pass/fail from a mock of a nonexistent orchestration layer.

## Evaluated wording for paraphrased caller questions

The scenario catalog quotes some questions verbatim and describes others by role and intent. For the latter, use the following **evaluated test wording** while retaining the scenario's original fixture and constraints. These strings are test inputs, not claims that the earlier persona catalog used these exact words. Keep optional caller keywords and trusted host context as separate fields. A demonstrative phrase such as “this component” or “this merge” requires an explicit context fixture; it is never an invitation to invent one.

| RS | Evaluated caller question |
|---|---|
| 05, 15, 19, 20 | “At the pinned source revision, how many ACs are reachable through TQ-500f covered_by links, excluding only TQ-500f itself, including both L2 and L3 descendants, grouped by work_status?” (exact `RQE-01` question) |
| 07, 18 | “Do we already specify what happens when research lacks required inputs? Show the relevant criteria.” (RS-01 question; RS-07 caller keywords remain separate) |
| 09 | “Which ADRs and contracts govern adding a retrieval operation, and what must remain compatible?” |
| 10 | “Which fixtures distinguish no matching tests from unsupported source mapping, with positive and negative controls?” |
| 11 | “Which canonical AC records at this revision directly declare depends_on: TQ-500f-2? Give only one-hop incoming declared dependencies, not all potentially affected code.” (exact `RQE-03` question) |
| 13 | “If evidence provenance changes, which consumers, ACs, and tests need review?” |
| 14 | “Which layer caused the test-writing question to return ok without done/todo counts, and what evidence establishes that?” |
| 16, 27 | “Which completed KM-500 ACs have proof through the real CLI or kernel, and which rely on helpers, scripted Jev, or unrun live checks?” |
| 17, 23 | “Can the current catalog answer which tests cover this component? If not, is the query missing or is the necessary data missing?” |
| 21 | “Has this merge reached the graph? Which source revision is published, and are semantic results ready?” |
| 22 | “What is the exact title and criteria source locator for KM-500c-2?” |
| 24 | “Which test files are directly declared for git_vcs_operations?” |
| 25 | “Does this proposed retrieval behavior contradict an existing AC or ADR? Which clauses need review?” |
| 26 | “Which unfinished requirements should we prioritize next for the Stable Portable MVP, and why?” |
| 28 | “Why did retrieval return ok without the requested work statuses, and where is its Langfuse trace?” |
| 29 | “Where does work_status travel from AC YAML into returned evidence?” (RS-12 question) |

## Independent oracle basis and scoring rules

The existing [source-reviewed specification](2026-10-01-repository-query-evaluation-cases.json) pins Git source `9d11594782abfb417d0f3a826bfb1f91f3a523ac`; the [runnable adaptation](2026-10-01-repository-query-evaluation-runnable.json) retains all twelve `RQE` IDs. The [independent report](2026-10-01-repository-answer-acceptance.md) records 12/12 executed and passed for that historical bounded corpus. Preserve those results and identities. New runs must report their own source, actor, backend, raw output, assertions and denominator; they do not inherit historical success. For new working-tree fixtures, pin copied bytes/content hashes and record dirty/revision identity separately.

The [fresh immutable-source oracle](2026-10-02-retrieval-active-source-oracle.json) separately inspects Git commit `59269e024e4d0290b68b03d0d382745966e67e29`, the source reported by the hosted graph during this test effort. It independently re-derives the same TQ-500f totals and direct dependencies, and records the current KM-500c-2 file hash and seven declared test references. Use this artifact for requests actually pinned to that commit; never silently carry the historical `RQE` oracle onto another source revision. The oracle is source expectation, not a retrieval output or proof that the hosted graph served it.

Reusable fixed oracles from the pinned source:

| Oracle | Independent expected fact and control |
|---|---|
| O1 / `RQE-01-P/N` | TQ-500f `covered_by` descendants, excluding only root: **15** unique L2/L3 ACs; **5 done, 10 todo**, if every `work_status` is available and enumeration complete. Terminal leaves are **11**. Withhold `work_status` while retaining lifecycle `status=active`: counts by work status become unresolved, not zero. Full ID set and source anchors are in the reviewed case JSON. |
| O2 / `RQE-02-P/N` | Canonical `KM-500c-2` `/criteria` at source SHA; scalar SHA-256 `9cfea912e97757a50beaab42e39ccfd82dd6f2bbf0d6e9425daf3e1d9e2617d3`. It explicitly separates successful build, query execution and answer assessment and distinguishes zero, contradiction and insufficiency. A clipped excerpt omitting those clauses cannot satisfy the question. |
| O3 / `RQE-03-P/N` | Exact one-hop incoming `depends_on: TQ-500f-2` IDs: `TQ-500f-2-i`, `TQ-500f-2-ii`, `TQ-500f-3-i`, `TQ-500f-5`, `TQ-500f-6` (five). Four disclosed rows marked partial have no exact total. No transitive code impact follows. |
| O4 / `RQE-04-P/N` | `KM-500c-2` has seven declared test references in the reviewed corpus. Declarations alone give no executed proof. The separately supplied historical report says two local Neo4j synthetic-fixture checks and one Aura public proof at `9f70de80ebcafe59ff55cce6732deb92069f9541`, scripted Jev and partial research; live external Jev was not run. The report's tested SHA is not the source SHA of the AC corpus. |
| O5 / `RQE-05-P/N` | Missing operation over supported mapped Test/`covered_by` data is a bounded query-build opportunity. If Test or `covered_by` mapping is absent, query build alone cannot repair it. Denial, outage and completed empty result are separate controls. |
| O6 / `RQE-06-P/N` | Prior standalone local receipt reported 16 `ok`/untruncated requests, 15 descendants and absent `work_status`; it supplied no verified Langfuse trace. Its path was mutable and is retained only as a historical observation snapshot in the reviewed JSON. An unavailable retrieval has unknown cause without matching diagnostics, no answer count and no fabricated trace URL. |

For every run, keep **execution status**, **original-question fulfillment**, **population completeness**, **source/field identity**, **proof strength**, and **observation state** as separate scored fields. A typed operation can pass its contract yet leave the question unanswered. An oracle must never fill actual output. When a source or provider prerequisite is unavailable, record `not_run` with the prerequisite; do not use a synthetic pass in its place. Grade forbidden wrong-answer shortcuts as well as positive facts.

## Per-scenario feasibility

| RS | Present-day route to exercise, if any | Independent oracle or controlled fixture; decisive target limit |
|---|---|---|
| **01** | **Public answer slice:** scripted-Jev kernel research may receive verbatim BA-02 question. Direct exact AC lookup tests only a narrower fact. | O2 and canonical required-input criteria for actual clauses. No caller backend/operation choice is allowed in the target. Today’s graph research does not offer the target's full search/navigation menu; do not award full RS-01. |
| **02** | **Public answer slice:** kernel research run/resume with scripted Jev and actual pending human interaction; compare run ID/state revision before/after. | O1 defines root-excluded versus 11 terminal leaves. The initial vague question has no authoritative population until clarification. Never score an invented `TQ-500f` or a second run as successful continuation. |
| **03** | **Public answer slice:** exact `KM-500c-2` lookup and `/criteria` disclosure; kernel research with controlled Jev may test selection. | O2 source scalar and locator. Current direct route can prove exact content but cannot prove target one-attempt shared comparison. No claim that untried methods lost. |
| **04** | **Target absent:** proposed automatic advisory strategy read/applicability is not the current approved DecisionRecord. | Two deliberately different source/version advice fixtures would be required. Current permission/manifest checks can be lower-layer controls; do not store advice or grant scope to simulate target behavior. |
| **05** | **Public answer slice:** explicit descendant operation with `answer_requirements`, plus conflicting direct-child/leaf variants. | O1; require all 15 source-backed work-status rows and complete scope for exact counts. Query-title match, `status` substitution and direct-child answer are wrong. Caller-question routing remains controlled, not a target catalog-contract proof. |
| **06** | **Lower layer:** current kernel can clarify or use known arguments; proposed generic typed host argument preparation and `judge-inputs` are absent. | Fixture has two plausible canonical IDs; only an observed, justified binding may execute. Score existing clarification separately; no auto-prepared argument pass. |
| **07** | **Target absent:** existing native retrieval may accept search terms, but the selected search child and known-term bypass into shared comparison do not exist. | Caller-provided three terms are input, never factual evidence. A native candidate result alone is not target term-origin/contract/shared-comparison proof. |
| **08** | **Target absent:** optional model-neutral five-term generation/validation route is not built. | Controlled valid output must be five distinct nonempty terms; four/duplicate/stale/foreign-contract output must not search. No provider call or fake generator pass. |
| **09** | **Target absent:** keyword/vector target methods are not jointly dispatched and compared in one question run. | ADR clause and schema locator must remain separately attributed; vector readiness must be established from serving manifest. Current sibling research behavior is not the specified common comparison. |
| **10** | **Target absent:** no shared two-search attempt collection/continuation. Existing outage/result retention checks are **lower layer** only. | A cited keyword fixture plus controlled vector timeout; the timeout is neither empty success nor reason to erase the keyword evidence. Do not claim cross-method fallback was run. |
| **11** | **Public answer slice:** registered direct-dependents operation; target Jev-selected graph frontier is absent. | O3 exact five one-hop IDs and source locators. Reverse direction, hierarchy-as-dependency and transitive/code-impact claims fail. A correct direct query is narrower than target navigation. |
| **12** | **Lower layer:** immutable source disclosure and supplied code-quote assessment can inspect a named mapping; folder/file frontier navigation is absent. | Pin canonical loader/disclosure/code file bytes and exact line locators independent of output. File presence alone cannot prove field flow/call graph; do not award a traversal pass. |
| **13** | **Target absent:** no offered graph/file traversal frontier with visited-cycle checkpoint. Current cursor and cumulative-budget controls are lower layer. | Deliberate A→B→A and unvisited C frontier; re-reading A/B or resetting read/depth/time/byte budgets fails once implementation exists. |
| **14** | **Target absent:** no target observed file-frontier validation. Path/source-byte safety can be probed below the journey. | Deliberate root escape or changed working-tree file plus one earlier valid excerpt. A revision/dirty label alone does not pin bytes; prior evidence must survive refusal. |
| **15** | **Public control slice:** current population/continuation requests can demonstrate that a page is partial; target traversal coverage is absent. | O1 and O3 partial controls. `known_count`/final page alone cannot produce `exact_total`; no discovered subset proves absence. Label current page check, not graph/folder walk. |
| **16** | **Target absent:** graph traversal → shared compare → advisory record → different method is not wired. Current proof assessment can separate declarations from supplied report. | O4. Seven declared tests do not become executed proof; report has its own tested SHA and scripted actors. Award only the narrower proof-level assessment. |
| **17** | **Target absent:** no common Jev comparison across registered query/search/traversal attempts. | Controlled graph link and file-manifest attempts each omit a required component-to-tests path/coverage fact. Preference among incomparable scopes is not a causal method win. |
| **18** | **Target absent:** no shared selected-evidence combination/deduplication with per-attempt provenance. | Same canonical AC from two attempts and one distinct ADR; dedup may not erase either citation or merge revisions. A unit dedup helper would be lower-layer only. |
| **19** | **Public control slice:** explicit `answer_requirements` plus withheld `work_status` in public retrieval/evaluator. | O1 negative. Execution may be `ok`, but done/todo remains unresolved; lifecycle `status=active` cannot substitute. Strong wrong-answer discriminator. |
| **20** | **Public answer slice:** full descendant operation through public service/CLI with sufficient budget. | O1 positive only at the pinned corpus: 15 unique root-excluded L2/L3 descendants, 5/10 status split; 11 terminal leaves. Verify all pages and fields before exact total. Does not prove target M:`combine`/`assess` orchestration. |
| **21** | **Lower layer:** current diagnosis/observation surfaces can show requested versus published SHA and missing trigger evidence; target typed wording handoff/acceptance is absent. | Pin manifest and actual merge-trigger receipt independently; no receipt means trigger unverified. Candidate wording cannot invent a verified trace or job run. |
| **22** | **Public answer slice:** direct exact lookup can return structured criteria/locator without synthesis. | O2. Current direct no-Jev behavior is useful, but does not establish target conditional `dispatch-wording` bypass transition. |
| **23** | **Public control slice:** kernel source-fit/build decision with controlled manifests; public evaluator O5 positive/negative. | O5 three independent states: fact absent, mapping/disclosure missing, operation missing over supported data. Only last may build; completed zero, outage and denial remain distinct. |
| **24** | **Public control slice:** existing governed query-growth kernel with scripted host/coder/human, trusted bounded candidate and activated local catalog; target return into common comparison absent. | O5 plus [candidate example](../../knowledge/examples/component_tests_candidate.json) and separate admission proof. Verify source pin, candidate digest/permissions, same-run resume, rejected candidate never executes. Do not run actual coding/provider or claim proper-query architecture resolved. |
| **25** | **Public control slice:** completed-empty versus unavailable, denied and exhausted states via direct/controlled kernel routes; target alternate-method continuation absent. | O6 unavailable control; a single failed query is not evidence of no conflict. If all routes denied, outcome names actual block without fabricated zero. Do not claim multi-method retry succeeded. |
| **26** | **Lower layer:** explicit-policy readiness assessment and existing initial clarification; target clarification *after* retained multi-method evidence is absent. | Canonical priorities/status plus supplied ranking policy are required for a recommendation; without policy or deployment proof, report unresolved. Do not invent benefit weights. |
| **27** | **Public control slice:** response/continuation budget tests can return partial evidence. | O1/O4 with intentionally insufficient byte/result/time budget. Keep cited proof levels and unknown remainder; budget must remain cumulative. A sampled set is not “all completed ACs.” |
| **28** | **Lower layer:** current diagnosis can distinguish missing field and unverified trace; proposed automatic advisory strategy storage is absent. | O6 plus separate source excerpt if supplied. No remote trace URL or incident root cause without matching proof. Never label a current approved DecisionRecord as automatic advice. |
| **29** | **Target absent:** no target `validate → nonreading → retain` frontier route or common comparison. | Controlled return/switch/clarify/stop before read should preserve attempts/frontier/budget and skip both read and post-read judgment. Current direct no-read response is not evidence of this transition. |

## Suggested execution order and report shape

Run the original twelve `RQE` cases first as a retained baseline, recording actual output and a fresh denominator. Then exercise `RS-02,03,05,19,20,23,25,27` through public routes with controlled actors and source-pinned oracles; `RS-11,15,22,24` are useful narrower follow-ups. Finally record the remaining target transitions as `unsupported/not_run`, with any lower-layer probes attached separately. A source or provider prerequisite should be explicit for each unrun case. Do not turn 29 catalog entries into a 29-pass denominator by counting controls as full scenarios.

For each scenario, save `scenario_id`, verbatim question, fixture and independent-oracle reference, source revision plus byte hashes, entry point, actor labels, budget, raw request/response or run/checkpoint path, actual execution outcome, factual answer assessment, observed behavior subset, unsupported target steps, forbidden-claim checks, verdict and limitation. The raw output must be inspectable so a reviewer can tell whether the system answered, refused honestly, hallucinated or broke before answer formation. This map does not prescribe an implementation or modify the target product flow.
