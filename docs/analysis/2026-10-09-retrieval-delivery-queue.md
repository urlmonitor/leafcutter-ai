---
title: Retrieval delivery queue and acceptance gates
description: Finite sequential repair plan for the saved retrieval scenarios and persona questions, with separate publication, selection and answer-quality evidence.
type: explanation
status: active
created: '2026-10-09'
last_updated: '2026-10-10'
components: [knowledge_management, decision_kernel]
related_docs:
  - docs/analysis/2026-10-02-retrieval-scenarios.md
  - docs/analysis/2026-10-01-repository-query-catalog.md
  - docs/reference/knowledge-retrieval-answers.md
  - docs/how-to/kernel-query-growth.md
---
# Retrieval delivery queue

This is follow-on work after [PR #1126](https://github.com/urlmonitor/leafcutter-ai/pull/1126), merged to canonical source `2a8ebc87ce937a0a2fec65ab26220f79a72e4859`. Publication is proven; the first live question batch exposed an interpretation defect before issue 02. The narrow issue 01a interpretation repair is accepted; its remaining live query-selection failure is assigned to queued issue 02. The original issue 01 whole-question exit remains unmet, and later issues are worked by an expert with an independent evaluator, one at a time. This plan adds no general planning workflow.

## Finite scope and evidence

The sources are the [29 saved scenarios](2026-10-02-retrieval-scenarios.md), the [25 persona questions across eight families](2026-10-01-repository-query-catalog.md), the [historical execution map](2026-10-02-retrieval-scenario-execution-map.md), and the [twelve-case runnable pack](2026-10-01-repository-query-evaluation-runnable.json). Preserve their original wording and dated evidence. The 25 questions are individual examples, not 25 distinct families. The 29 scenarios, 25 questions and twelve evaluations overlap and must not be added into one pass-rate denominator.

For new population fixtures, use canonical structural-parent descendants. The historical execution map's `covered_by` count wording is not the new hierarchy oracle. Pin the actual corpus and independently calculate expected membership, levels and status counts before execution; historical 15-descendant and five-done/ten-todo values are not promises about a newer source.

[Saved public evidence](../../reports/retrieval-public-2026-10-09/index.html) retains the original 0/5 complete positives and passing stale-source control, followed by 2/2 exact-AC source-disclosure cases on the separately fingerprinted repair. These use real Jev with bounded local actual-source storage, not live Aura. The [blind interpretation result](../../reports/retrieval-public-2026-10-09/needs-evaluation/controller-envelope-repair/summary.json) is 12/12 original cases plus 4/4 frozen holdouts; it proves interpretation separately from retrieval. Historical October 3 evidence remains unchanged.

Issue 00, the pre-release target-set and paid-usage defects, is fixed in the reviewed snapshot. The release review reports 14 focused target/accounting cases and 89 existing regression cases passing; these are controlled checks, not another real-provider evaluation. [Target obligations](../../tests/knowledge/test_public_retrieval_target_obligations.py) cover retained original identities, saved custom seeds, missing members and paid usage on refused operations. [KM-500e-1-i](../acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500e-1-i.yaml) remains `approved / in_progress` because its wider public-route obligations are not all proven.

## Rules for every delivery slice

- Freeze question, fixture, source, expected terminal class and independent oracle before the expert sees outcomes. A complete answer needs the requested facts, population and citations; query execution alone is insufficient.
- A focused clarification is correct only for missing meaning or permission that changes the answer. Model uncertainty is not missing user intent. Unsupported, stale, unavailable, denied and budget-limited results must retain their actual reasons.
- Honest unsupported is a passing result only for a designated negative or out-of-scope control. It cannot complete an intended positive feature that is still missing. Proper retrieval does not promise answers to arbitrary questions without relevant evidence.
- Preserve the original question, targets, required fields, source pins, authority, cumulative budgets, usage and useful evidence across every route and wait. Never lower confidence gates or weaken expected answers to obtain a pass.
- Record public entry point, source and tested code identities, catalog/query/model settings, actual requests, outputs, citations and review verdicts. Distinguish controlled, replayed-host, fresh-provider, local-storage and Aura evidence; keep not-run and unknown visible.
- Each issue exits only after independent review of its positive and negative controls. Reuse existing approved ACs; add a narrowly scoped child only when required behavior is absent. Tentative IDs below are unreserved, not authored or approved ACs. Recheck the current store before assigning one.
- Broad AC statuses change only with evidence for their full scope. Completing one slice of an AC does not complete unrelated security, telemetry, lifecycle or deployment obligations in that AC.

## Ordered slices

### 01 — Publish the canonical source to Aura: publication proven, answer exit blocked

- **ACs and entry:** [KM-500d-2](../acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500d-2.yaml) is already `approved / in_progress`; reuse the completed `KM-400e-5` publication invariant. Enter with the reviewed release and actual canonical workflow event; no status edit is needed merely to start.
- **Work and exit:** Diagnose the real validation/publication job, preserve the last valid generation on failure, and establish the actual source SHA, generation and graph readiness. Execute the two exact-AC public questions against that published source in both catalog modes, plus a stale/unavailable control. Record separate semantic readiness rather than implying graph publication populated vectors.
- **Review gate:** Match canonical event/run, published source and retrieval citations. Manual sync is separate evidence. Current CI status, credentials, permissions or publication failure remain explicit; never copy local-storage proof into an Aura result. Broader KM-500d-2 obligations remain open where untested.

The [canonical publication receipt](../../reports/retrieval-aura-2026-10-09/publication-receipt.json) records push workflow [37989481802](https://github.com/urlmonitor/leafcutter-ai/actions/runs/37989481802), source and independently checked writer checkout `2a8ebc87ce937a0a2fec65ab26220f79a72e4859`, generation `72a3b693c251e51789966795c5ecd58acc83170b815ee90582a5000741a27887`, mapper 7, 10,174 nodes and 26,987 edges. Graph publication passed; `semantic_ready` remains false.

The [closed live batch](../../reports/retrieval-aura-2026-10-09/runs/published-2a8ebc87/review.html) used real Aura and Jev with fresh blind host packets. All three positive interpretations omitted authored `test_spec`. Retrieval matched chosen canonical criteria in 3/3, but whole-question correctness was 0/3. Public outcomes were partial, partial and completed; the stale-source control passed 1/1. Seven Jev calls and six accepted host submissions are recorded. The frozen baseline remains failed; publication alone does not close the question-answer exit.

### 01a — Interpret verification obligations without adding unrelated fields: narrow repair accepted

- **ACs / scope:** Amend existing approved, in-progress `KM-500e-1-i`; reuse `KM-500e-1/e-2`, `KM-500f-2` and quality gate `KM-500a-4`. No new child, broad completion or source-fixture AC status change is needed. Issue 02's accepted design remains queued unchanged.
- **Repair:** Clarify the existing host/catalog meanings: verification obligations need canonical `criteria` plus authored `test_spec`; acceptance-only, specification-only, declared-reference and status requests retain their narrower meanings. Context cannot add unrelated obligations. No literal-ID hack, all-fields default or deterministic field injection is authorized.
- **Frozen exit:** [IP01–IP12 contrasts](../../reports/retrieval-needs-precision-2026-10-09/cases.json) and their [bounded evaluation plan](../../reports/retrieval-needs-precision-2026-10-09/plan.json) cover the original and changed-ID question, a different-target paraphrase, narrower requests, equivalent linked-test representations, whole-document intent and unavailable execution-proof meaning. Independent fresh host interpretation is graded separately from controlled transport. Whole-document interpretation does not establish downstream support. Re-run the unchanged four Aura cases after review; retain actual sources, citations, limitations and any non-complete outcomes.
- **Evidence discipline:** The Oct3 oracle explicitly allowed an optional test specification and stays historical. The current Aura oracle requires the two authored fields and is not weakened. Existing failed receipts remain immutable; new prompt/catalog versions and outcomes are separate. The evidence below accepts the narrow interpretation repair; these amendments do not complete broader retrieval obligations.

The [closed first precision batch](../../reports/retrieval-needs-precision-2026-10-09/stage1/review.html) passed 10/12 interpretations, including all three complementary-field positives. IP07 retained a redundant reference-field plus relationship obligation; IP11 honestly identified unavailable CI execution evidence but added an unnecessary investigative field. This is interpretation-only evidence: no graph retrieval or new Aura outcome is implied. Revision2 distinguishes indispensable answer facts from optional discovery hints, and declaration values from requested linked records or populations. Four independent holdouts were frozen before that revision; their exact new CI-evidence case disallows investigative content, while historical IP11 keeps its original allowance. No original case, gold or outcome is rewritten; that first batch remains 10/12.

The [closed revision2 semantic review](../../reports/retrieval-needs-precision-v2-2026-10-09/stage1b/review.html) passed **16/16 fresh host interpretations**: the unchanged twelve cases plus four independently frozen holdouts. All sixteen finite checks and both manual execution-gap reviews passed. The [machine-readable review](../../reports/retrieval-needs-precision-v2-2026-10-09/stage1b/review.json) and [closure record](../../reports/retrieval-needs-precision-v2-2026-10-09/stage1b/closure-integrity.json) retain the evidence. The batch used zero Jev calls, zero graph calls and no retries; model identity and token counts are unknown. This proves the bounded interpretation gate only, without retrieving evidence or establishing full-document, exhaustive-population or actual CI-execution support. The earlier prepared run remains [not run before explicit permission](../../reports/retrieval-aura-2026-10-09/runs/precision-v2-2a8ebc87/approval-block.json); its automatic rejection before process creation adds no answer-quality score. After human approval, the separately pinned committed-runtime batch below executed once. Historical 10/12 and live 0/3 outcomes are preserved.

The [closed live retest](../../reports/retrieval-aura-2026-10-09/runs/precision-v2-44406d9/review.html) used runtime `44406d923e2a0e2f40079a317135d0736534c654`, the same canonical source and generation, real Aura and Jev, and fresh blind host packets. It achieved **4/4 sufficient interpretations, 2/3 correct complete positive answers and 1/1 passing stale control**, with six Jev calls, four accepted host results and no retries. A01 and changed-ID A03 returned exact canonical `criteria` and authored `test_spec` with matching field locators and immutable source pins. A02 retained both fields and its original target, but `get_entities` received 0.71 probability below the unchanged 0.80 gate (confidence 0.64 exceeded 0.50); it returned partial without retrieval or evidence and retained its one paid selector call. The [remaining-selection receipt](../../reports/retrieval-aura-2026-10-09/runs/precision-v2-44406d9/remaining-selection-issue.json) assigns that failure to issue 02. This paired observation does not establish that enabling the catalog caused the failure. Independent source/closure review accepts the narrow interpretation repair; the full three-positive live gate, original issue 01 whole-question exit and broader ACs remain open. No general count, traversal, full-document, CI-outcome or vector-readiness claim follows.

### 02 — Make eligible operation choices match the requested population: queued

- **ACs / dependency:** After 01, reuse `KM-500a-2`, `KM-500e-1`, `KM-500e-1-i` and quality gate `KM-500a-4`; tentative child `KM-500a-2-i` only if new clauses are needed. Completed selection primitives retain their existing evidence; adding unfinished scope must be visible in parent status.
- **Accepted design:** Before the existing single Jev call, remove only operations provably incompatible with typed answer requirements and supply compact candidate-fit facts. Known population execution supplies exact-scope metadata; saved-recipe prose alone does not. Do not exclude candidates merely because a requested field needs source hydration or evidence may be truncated. Jev chooses the remaining semantic option with the existing 0.80 selected-probability threshold unchanged.
- **Exit / independent review:** Freeze P03/P04, paraphrases and changed-scope controls. Both catalog modes execute the proper structural-descendant read with original levels, inclusion and work-status obligations; wrong population, missing input and provider-failure controls remain distinct. Preserve `selection_uncertain` separately from unsupported and user ambiguity. No new retry workflow or forced human clarification; no count-completeness claim from this gate. Qualify KM-500a-1's broad uncertainty wording if necessary.

### 03 — Deliver a complete bounded count or an honest incomplete aggregate: queued

- **ACs / dependency:** After 02, reuse `KM-500e-3`; a public accumulation child such as `KM-500e-3-i` is tentative. RS-05/15/19/20 supply population and incomplete-result controls.
- **Exit:** A reviewed source population yields its independently calculated distinct total and work-status groups when cumulative limits permit complete enumeration or a verified aggregate. Root-only exclusion and exclusion of all parents differ; unknown statuses remain unknown. Duplicate rows, cycles, truncated pages, missing members and the default six-result/15-descendant mismatch cannot yield a false complete count.
- **Review gate:** Test actual public requests, saved continuation state and source membership, including a genuinely complete positive and deliberately insufficient budgets. A larger default alone is not completeness proof; a final page is not the full aggregate.

### 04 — Clarify genuinely ambiguous population meaning: queued

- **ACs / dependency:** After 03, reuse `KM-500a-1`, `KM-500e-1` and child `KM-500e-1-i`; any extra continuation child remains tentative. RS-02 and baseline P05 distinguish a named family from a topic across the project.
- **Exit / review:** Ask only the missing population/inclusion choice, resume the same run once, and preserve prior evidence and budgets. Explicit sufficient scope is not asked again. Stale or authority-widening replies fail. A topic answer may depend on 06; a legitimate clarification does not by itself prove topic discovery works.

### 05 — Prepare missing query inputs and optional search terms: queued

- **ACs / dependency:** After 04, reuse `KM-500a-1/a-2` and `KM-500e-1`; proposed argument/term preparation children are not yet allocated. RS-06/07/08 are the frozen entry cases.
- **Exit / review:** Caller-supplied suitable terms bypass generation. Otherwise an interchangeable host LLM supplies five distinct nonempty terms through the existing typed kernel wait; generated terms remain search inputs, not facts. Query arguments bind only observed permitted candidates to the selected contract. Invalid, stale, invented or scope-changing responses never execute a query; duplicate resume does not duplicate execution.

### 06 — Discover a topic population with an explicit membership rule: queued

- **ACs / dependency:** After 05, reuse `KM-500e-1/e-3/e-4`; allocate a narrow discovery child only after its new contract is reviewed. BA-01 and RS-01/02/05 are intended positives, not permanent unsupported controls.
- **Exit / review:** Freeze the meaning of topic membership, corpus boundary, hierarchy filter and required completeness. Discover the independently reviewed members with attributable source evidence. Search candidates may support examples but do not establish an exhaustive topic count; corpus or matching-rule gaps remain visible without silently substituting a component or named root.

### 07 — Navigate declared graph relationships: queued

- **ACs / dependency:** After 06, reuse `KM-500f-1` and bounded knowledge primitives; new traversal children remain proposed. RS-11/13/15 define direction, cycles and incomplete traversal.
- **Exit / review:** Jev chooses among actually observed permitted frontier items and follows supported edge types/directions, retaining visited IDs and cumulative depth/fanout limits. A completed direct-dependency positive differs from transitive/code-impact claims. Cycle and exhausted-frontier controls cannot repeat completed reads or imply exhaustive absence.

### 08 — Navigate repository folders and source files: queued

- **ACs / dependency:** After 07, reuse `KM-500f-4` and `KM-400d-2/d-3/d-4`; proposed file-navigation child scope stays separate from graph traversal. RS-12/14/29 are entry cases.
- **Exit / review:** Use observed folders/files and immutable source bytes or recorded content hashes; enforce permitted roots and stale-path rejection. File membership never invents a call/dependency edge. Finish, alternate-method, clarification and stop decisions made before a read cause neither a read nor a post-read judgment or read charge.

### 09 — Compose multiple routes and recover from a useful dead end: queued

- **ACs / dependency:** After 08, reuse `KM-500c-3` no-progress rules; a narrowly scoped multi-method child is proposed, not allocated. RS-09/10/16/25/27 exercise sibling success, failure and budgets.
- **Exit / review:** Existing LangGraph flows retain separate attempt identities, useful sibling evidence, original obligations and cumulative usage. Jev can select compatible multiple methods or return to a changed route after a bounded dead end. Unchanged repeated attempts stop; unsupported, outage and denied access are not no-match success or automatic build permission.

### 10 — Compare attempts, combine evidence and rank it: queued

- **ACs / dependency:** After 09, reuse `KM-500e-2` and `KM-500c-2`; new comparison/merge children remain proposed. RS-17/18/19/20 supply controls.
- **Exit / review:** Judge observed attempts against the same original question, permitting ties, complementary results or no winner. One attempt cannot beat an untried alternative. Deduplication retains all provenance and keeps differing source versions separate. Relevance does not erase missing fields, manufacture complete coverage or double-count identities.

### 11 — Answer the remaining persona families with correct proof levels: queued

- **ACs / dependency:** After 10, reuse `KM-500e-2`, `KM-500f-2/f-3/f-4/f-5` and `KM-500g-1/g-2`; create only missing composition children. RS-21/22/26 and all RQ families define the bounded scope.
- **Exit / review:** Structured facts can bypass extra wording; optional LLM prose retains citations and limitations. After-evidence clarification preserves findings. Policy-backed prioritization differs from canonical priority; declared tests differ from inspected assertions and executed proof; source field-flow explanation differs from incident diagnosis. Evidence for contradictions, dependents and recommended regressions must support the actual claim, not a filename or guessed complete call graph.

### 12 — Store and consult advisory method outcomes: queued

- **ACs / dependency:** After 11, reuse `KM-500a-3/e-4`; a new advisory-memory child is proposed. RS-04/28 are entry cases. Human-approved DecisionRecord publication is a separate authority contract.
- **Exit / review:** Record attributable question/attempt/method/source/model/budget observations and compare applicability before suggesting later methods. Stale or incompatible advice cannot grant authority, choose for Jev, copy an old answer or train a model implicitly. Storage failure preserves the answer and reports only the failed observation.

### 13 — Prove actual query authoring, admission and reuse: queued

- **ACs / dependency:** After 12, reuse `KM-500b-4/b-5` and `KM-500e-4`; both b-4 and b-5 are `approved / todo`. RS-23/24 require more than a supplied prewritten candidate.
- **Exit / review:** Distinguish absent source facts, unsupported mapping and a genuine missing operation. A real coding-agent handoff produces a candidate which independent verification admits only under existing permission; the same research resumes once and a fresh process reuses the pinned version. Test incompatibility, failed verification and rollback without granting write authority to read-only research.

### 14 — Support long material and vector routes where declared available: queued

- **ACs / dependency:** After 13, reuse `KM-500d-4` (`approved / todo`) and `KM-400c-4`. RS-09's vector-ready positive needs actual prerequisites; keyword-first retrieval remains distinct.
- **Exit / review:** Approved long-source chunks retain parent/locator identity and budgeted deduplication; incompatible model/generation settings cannot claim semantic readiness. Demonstrate an actually ready vector route and its unavailable counterpart through the offered interface. Graph-ready alone does not satisfy the positive case.

### 15 — Close the finite public acceptance matrix and agent walkthrough: queued

- **ACs / dependency:** After 14, reuse `KM-500a-4`, `KM-500d-1/d-3` and `KM-500g-3`. These remain pending; no broad quality parent is done by this plan.
- **Exit / review:** Execute the reviewed matrix through the declared public interface on an attributable deployment. Every intended positive has a supported answer path; each deliberate clarification/negative/partial control has its expected honest outcome. Publish actual denominators, unmet prerequisites and trace visibility, plus an agent-readable walkthrough of requests and responses. Recheck changed slices rather than relabeling older source/model receipts as current.

## Coverage assignment

Every scenario has a primary delivery owner below; cross-issue dependencies still apply. This assigns work, not passing verdicts.

| Primary issue | Scenario IDs from the saved catalog |
|---|---|
| 02 | RS-05 |
| 03 | RS-15, RS-20 |
| 04 | RS-02 |
| 05 | RS-06, RS-07, RS-08 |
| 06 | RS-01 |
| 07 | RS-11, RS-13 |
| 08 | RS-12, RS-14, RS-29 |
| 09 | RS-09, RS-10, RS-16, RS-25, RS-27 |
| 10 | RS-17, RS-18, RS-19 |
| 11 | RS-21, RS-22, RS-26 |
| 12 | RS-04, RS-28 |
| 13 | RS-23, RS-24 |
| 15 | RS-03: retain the already demonstrated exact-source slice and validate the complete target scenario |

Every original persona question is assigned once to its existing answer family below. Issue 15 verifies all 25, including variants not separately named by an RS scenario.

| Family | Exact persona IDs | Main delivery dependencies |
|---|---|---|
| RQ1 Inventory/status | BA-01 | 02–06 |
| RQ2 Requirements/contracts | BA-02, BA-05, ITPO-01, CODER-02, QA-01 | 05, 06, 10, 11, 13 |
| RQ3 Priority/readiness | PO-01, PO-02, PO-03 | 01, 03, 11 |
| RQ4 Dependencies/impact | BA-03, PO-04, PO-05, ITPO-02, CODER-03 | 05, 07–11 |
| RQ5 Implementation/field flow | CODER-01, CODER-05 | 08, 11 |
| RQ6 Proof/regressions | BA-04, CODER-04, QA-02, QA-03, QA-04 | 08, 11, 13 |
| RQ7 Query fitness | ITPO-03 | 02, 12, 13 |
| RQ8 Runtime/diagnosis | ITPO-04, ITPO-05, QA-05 | 01, 11, 15 |

## Status handoff

At the reviewed head, KM-500a-1/a-2/a-3, b-1/b-2/b-3 and c-1/c-2/c-3 are completed approved primitives; they do not claim the proposed combined journey. KM-500a-4, b-4/b-5 and d-4 are approved and todo. KM-500d-1/d-2/d-3, e-1 through e-5, f-1 through f-5 and g-1 through g-3 are approved and in progress. The existing e-1-i child remains in progress. The precision amendment preserves the existing AC statuses; this queue does not promote a planned test or prompt repair to done.

Publication and narrow interpretation acceptance are recorded above. Issue 02 owns the remaining A02 operation-choice failure on a separate delivery branch; the original issue 01 whole-question exit stays unmet until the unchanged positive question passes. The accepted eligibility design still needs its exact next-slice cases and source-bound oracle frozen before implementation; historical P03/P04 wording remains unchanged. The remaining queue is finite proposed delivery scope, with refinements recorded against the same persona/scenario IDs rather than an expanding promise to answer every possible question.
