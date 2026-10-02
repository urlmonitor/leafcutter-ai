---
title: Repository query catalog
description: Twenty five role questions grouped into proposed repository query families and an initial evaluation plan.
type: explanation
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components: [knowledge_management, decision_kernel]
---
# Repository query catalog

This discovery catalog preserves five questions from each of BA, PO, IT PO, coder and QA, then groups shared needs into eight query families. The questions are proposed recurring needs, not measured frequency, implemented capabilities or approved acceptance criteria. The proposed first evaluation batch tests six families before implementation decisions are made.

Technical observations refer to implementation commit `9d11594782abfb417d0f3a826bfb1f91f3a523ac`. Pending working-tree AC additions are not part of that published source. The linked [evaluation cases](2026-10-01-repository-query-evaluation-cases.json) are planned specifications; this discovery work does not execute them or establish passing results.

## Shared answer requirements

Every proposed answer contract needs the following information. This is a discovery recommendation, not a new implemented wire schema.

- **Scope:** repository and immutable revision; named IDs, component or family; matching method; direct children versus all descendants; inclusion of superseded requirements. Clarify natural-language concepts such as test writing instead of silently replacing them with a component.
- **Counting policy:** distinguish excluding only a selected family root from selecting leaves only. An L2 requirement can itself have L3 children. The earlier TQ-500f traversal found a root and descendants; excluding that root is not proof of a leaf-only result. Count unique canonical IDs, state the denominator and keep unknown totals unknown.
- **Field meaning:** lifecycle `status`, implementation `work_status`, requirement status and readiness are separate. Missing fields must be absent or explicitly unknown, never converted to todo, done or active by inference. State which source field supplies each requested value.
- **Provenance:** cite entity ID, source SHA, source path and exact field or locator. Graph generation, operation version/digest and retrieval ID identify how evidence was retrieved. Run receipts additionally need tested code revision, environment and time. Do not conflate an AC source revision with a test execution revision.
- **Completeness:** distinguish a complete answer, bounded partial answer, required data unavailable, unsupported query and failed retrieval. An `ok` retrieval response means execution succeeded; it does not establish that every requested field was supplied or that the original question was answered. Counts from truncated evidence are lower bounds unless completeness is independently established.
- **Evidence strength:** separate declared links, inspected assertions, executed proof and deployed behavior. Label inference and recommendation. A test path is not a passing run; a recipe admission receipt is not proof of general usefulness; a trace ID without accessible observations does not establish a failure cause.

A useful answer must distinguish four different gaps: the authoritative source never records a fact; the fact exists but is not projected/disclosed; the data is available but the registered query cannot express the operation; or the operation exists but has not been verified in the requested environment. Only the third is directly a missing-query opportunity. Clarification, access denial and outages are separate outcomes.

## Query families

| Family | Answer content and required fields | Scope and completeness rule |
|---|---|---|
| RQ1 Inventory and status | Matching AC IDs/titles, parent/level, components, explicitly requested status fields, grouped counts and missing-field counts. | Resolve topic membership, revision and root-only versus leaf-only selection before counting. Require exhaustive membership and fields for an exact total. |
| RQ2 Requirements and contracts | Exact criteria/clauses, IDs, governing ADRs, schemas, required fields, permissions, must-catch examples and relevant conflicts. | Distinguish exact ID retrieval from semantic reuse search. Compare a supplied proposal with cited clauses; a missing must_catch value means not specified. Never claim no relevant requirement from an incomplete search. |
| RQ3 Priorities and benefit readiness | Benefits, unfinished obligations, priority/readiness/work status, roadmap alignment, missing evidence and reasons for a recommendation. | Declare phase, release/installation and ranking policy. Missing value estimates or outcome links prevent an authoritative ranking. Declared done and deployment readiness remain separate. |
| RQ4 Dependencies and change impact | Directed dependency paths, changed contracts/requirements, affected benefits/consumers/tests and the reason each is included. | Specify source/target revisions, direction and traversal depth. Separate hierarchy from true blocking dependencies. A graph of declared links gives declared impact, not a complete code impact analysis. |
| RQ5 Implementation and field flow | Source modules/functions, field mappings, current extension points, requested versus returned fields, observed break point and remaining hypotheses. | Pin code and relevant run. Follow inspected source evidence; file references alone do not establish data flow. No actual runtime cause without matching runtime evidence. |
| RQ6 Proof and regression selection | Linked test IDs, asserted behavior, entrypoint, fixture/control data, real versus simulated actors, execution receipts, tested SHA and missing proof. | Distinguish requirements coverage, test declaration, source inspection and actual execution. Include positive and negative controls; explain each proposed regression rather than promising a complete suite from partial links. |
| RQ7 Query fitness | Available query purpose/input/result contracts, supported source kinds/fields, scope/bounds and the precise reason the question is or is not answerable. | A component-to-tests query must match the requested path semantics. Check source availability before proposing a new query; unknown mapping or absent required fields cannot be repaired by query naming. |
| RQ8 Runtime state and diagnosis | Requested/published SHA, graph/semantic readiness, actual trigger, errors, scope comparison, retrieval/run IDs, telemetry availability and the smallest justified rerun. | Require the intended deployment or specific run. No provider/trace access means unavailable evidence, not an invented trace or root cause. Manual synchronization does not prove a merge-triggered job ran. |

## Original role questions

The origin IDs preserve all 25 questions from the role-discovery exchange. Grouping does not replace or narrow an example.

| Origin | Family | Natural language example |
|---|---|---|
| BA-01 | RQ1 | How many ACs concern test writing, and what are their work statuses? Exclude parent requirements. |
| BA-02 | RQ2 | Do we already specify what happens when research lacks required inputs? Show the relevant criteria. |
| BA-03 | RQ4 | If query-result field semantics change, which requirements depend on that contract? |
| BA-04 | RQ6 | What proves KM-500c-2 is satisfied, including cases where retrieval succeeds but the answer is insufficient? |
| BA-05 | RQ2 | Does this proposed retrieval behavior contradict an existing AC or ADR? Which clauses need review? |
| PO-01 | RQ3 | Which unfinished requirements should we prioritize next for the Stable Portable MVP, and why? |
| PO-02 | RQ3 | What prevents us from saying KM-500 is ready for everyday use? |
| PO-03 | RQ3 | For KM-500b, which promised benefits are delivered, pending, or unsupported by evidence? |
| PO-04 | RQ4 | Which prerequisite would unblock the most approved KM-500 benefits? |
| PO-05 | RQ4 | Since the last accepted release, which promised behaviors changed and which benefits need another review? |
| ITPO-01 | RQ2 | Which ADRs and contracts govern adding a retrieval operation, and what must remain compatible? |
| ITPO-02 | RQ4 | If evidence provenance changes, which consumers, ACs, and tests need review? |
| ITPO-03 | RQ7 | Can the current catalog answer which tests cover this component? If not, is the query missing or is the necessary data missing? |
| ITPO-04 | RQ8 | Has this merge reached the graph? Which source revision is published, and are semantic results ready? |
| ITPO-05 | RQ8 | Why did retrieval return ok without the requested work statuses, and where is its Langfuse trace? |
| CODER-01 | RQ5 | Where does an AC field travel from canonical YAML through projection into returned evidence? Where should I add work_status? |
| CODER-02 | RQ2 | What must a coding agent submit for host.query_build, and which permissions and scope constraints apply? |
| CODER-03 | RQ4 | If KnowledgeRetrievalResult gains missing-field reporting, which callers, schemas, fixtures, and ACs need review? |
| CODER-04 | RQ6 | Before changing query activation, which tests protect permission checks, same-run resumption, and catalog reuse? |
| CODER-05 | RQ5 | Which layer caused the test-writing question to return ok without done/todo counts, and what evidence establishes that? |
| QA-01 | RQ2 | For KM-500c-2, what must tests demonstrate, and which plausible wrong implementation must they catch? |
| QA-02 | RQ6 | Which completed KM-500 ACs have proof through the real CLI or kernel, and which rely on helpers, scripted Jev, or unrun live checks? |
| QA-03 | RQ6 | If query activation changes, which regressions protect version pinning, permissions, resumption, and existing retrieval? |
| QA-04 | RQ6 | Which fixtures distinguish no matching tests from unsupported source mapping, with positive and negative controls? |
| QA-05 | RQ8 | This test failed with scope_mismatch: what expected and actual values differed, which contract was violated, and what is the smallest rerun? |

## Source availability and current capability

These are inspected implementation facts, not results of executing the 25 questions. The [canonical loader](../../knowledge/projection/canonical_loader.py) enables `acs`, `adrs` and `components`. Test/SourceFile nodes arise from referenced files; they are not a complete code, documentation or test index. AC entity properties include lifecycle `status`, while source disclosure targets `/criteria`. The [disclosure allowlist](../../knowledge/disclosure.py) does not expose work_status, priority, readiness, test specifications or roadmap metadata.

The [built-in operations](../../knowledge/adapters/neo4j_queries.py) support exact and selected one-hop questions. The [recipe model](../../knowledge/query_models.py) supports explicit seeds and at most two directed relationship steps; its filter properties are canonical_id, kind, status and decision_type. The [compiler](../../knowledge/query_compile.py) imposes fixed seed/fanout/result limits. This is not a global AC inventory, aggregation, arbitrary text-search or transitive code-analysis interface.

| Family | Authoritative sources to consult | What the current tool can and cannot establish |
|---|---|---|
| RQ1 | AC YAML hierarchy, component registry, status fields and immutable source revision. | It can retrieve known entities and declared component links. work_status and hierarchy/status aggregation are not currently an answerable complete contract; raw authoritative fields existing on disk do not make them retrievable. |
| RQ2 | AC criteria/test_spec/must_catch, ADR text, capability registry and versioned schemas. | Exact AC criteria and mapped ADR evidence are useful foundations. General requirement similarity/conflict detection, test-spec fields and full schema/host contracts are not indexed answer contracts. Missing source metadata must remain unspecified. |
| RQ3 | AC priorities/readiness/work_status, L0/L1 benefits, roadmap/current_outcome, release and deployment proof. | Names and declared relations alone cannot produce readiness or value ranking. Most required product fields and roadmap/operational evidence are outside the present projection/disclosure. Recommendations would need a stated policy. |
| RQ4 | Declared AC relations, revision diffs, code/schema consumers and test links. | Bounded declared-edge traversal is possible within permitted recipes. No general transitive closure, code-call/dependency graph or two-revision impact operation is established. Declared references must not be called exhaustive consumers. |
| RQ5 | Canonical loader/disclosure/query code, schemas and an attributable failing response or trace. | Source code exists for inspection, but the graph does not model its functions or data flow. The work_status omission is inspectable in source; a particular incident's cause still requires its actual request and evidence. |
| RQ6 | AC covered_by/test_spec, test source/fixtures, verified run receipts and environment records. | Declared AC-to-test paths are available where mapped. A callable anchor can belong to a relationship locator while the Test node identifies a file; neither is an executed case. Assertion inspection, fixture adequacy, actual run outcomes and actual versus simulated actors are not implied by those edges. Reports and test runs are not automatically ingested. |
| RQ7 | Trusted query descriptors, source manifest, field mapping/disclosure and requested answer contract. | The catalog exposes described operations, while generation manifests expose source readiness. Mechanism-level semantic capability can be advertised when generation semantic_ready is false; callers must inspect both. Field-level availability checks are still needed; an offered operation name alone does not establish answerability. Current missing work_status is a field/disclosure gap, not simply a missing aggregate template. |
| RQ8 | Active projection manifest, configured canonical branch/workflow, actual run/checkpoint/telemetry data and error artifacts. | Published SHA and readiness can be inspected. Standalone CLI does not inject telemetry; kernel retrieval has an observability integration, but results have no trace-URL field. Neither implies an accessible Langfuse trace, a complete runtime-event projection or an automatic explanation of a failed answer. |

Relevant source contracts include [roadmap](../roadmap.json), [query catalog](../../knowledge/query_catalog.py), [kernel query growth](../../integrations/query_growth.py), [source disclosure](../../knowledge/disclosure.py), [telemetry integration](../../integrations/knowledge_execution.py), and [retrieval evaluation](../../knowledge/evaluation.py). Existing evaluation measures entity-ID precision/recall, correction coverage, provenance, size and latency. It does not establish requested-field correctness, exhaustive counts, original-question answerability or trace completeness; its recorded status must be considered before interpreting scores.

## Proposed first evaluation batch

Prioritize one positive/control pair for each family below: 12 planned cases sampling six of eight families. This is not a representative benchmark of all 25 role questions. A positive case defines a meaningful target contract; it is not a promise that the current tool passes. Cases must distinguish known expected answers from currently missing capability, and a control must fail the same plausible wrong implementation rather than merely exercise another happy path.

| Priority and case IDs | Family and origin | Planned positive and control pair |
|---|---|---|
| 1; RQE-01-P / RQE-01-N | RQ1; BA-01 | Explicit TQ-500f root-excluded inventory of all L2/L3 descendants with complete work_status evidence, versus the same records with work_status withheld. This is not a leaf-only or repository-wide count. |
| 2; RQE-02-P / RQE-02-N | RQ2; BA-02, BA-05, ITPO-01, QA-01 | Exact KM-500c-2 criteria at the pinned SHA, versus an excerpt truncated before the clauses distinguishing successful execution from a sufficient answer. |
| 3; RQE-03-P / RQE-03-N | RQ4; BA-03, ITPO-02, CODER-03 | Complete incoming one-hop depends_on results for TQ-500f-2, versus a response omitting one dependent and explicitly marked incomplete. No transitive code-impact claim. |
| 4; RQE-04-P / RQE-04-N | RQ6; BA-04, QA-02 | KM-500c-2 declared test references plus a separately scoped historical acceptance report, versus declarations alone with execution evidence withheld. |
| 5; RQE-05-P / RQE-05-N | RQ7; ITPO-03 | A controlled missing component-to-tests operation over supported source data, versus the same missing operation with Test/covered_by mapping unavailable. The setup is hypothetical, not the current deployed catalog. |
| 6; RQE-06-P / RQE-06-N | RQ8; ITPO-04, ITPO-05, QA-05 | The historical local TQ field-gap receipt with no verified trace, versus a controlled unavailable envelope with no source pin or trace proof. Neither permits an invented Langfuse link or root cause. |

QA owns the exact inputs, independent oracles and wrong-implementation checks in the [planned evaluation cases](2026-10-01-repository-query-evaluation-cases.json). Oracle source inspection is allowed for designing expected results, but must never be substituted for actual tool output during a future evaluation. All cases remain not run until their real execution is recorded separately with revision, environment, outputs and failures. No real provider is authorized by writing this plan.

## Later evaluation cases

After the first batch exposes data and query gaps, extend to RQ3 priority/readiness recommendations with explicit policies and missing-value controls; RQ5 inspected code/data-flow answers and attributable incidents; RQ4 revision comparisons and broader consumer impact; RQ6 fixture and minimal regression selection; and RQ8 deployed merge/semantic-readiness and trace correlation. Add full real-Jev planning and coding-agent build/admission/resume cases only with the required provider authorization and clear separation from scripted proof.

The next decision is which answer contracts and source mappings to implement based on these cases. This catalog creates no ACs, code, executable tests, tickets, deployment changes or model-training plan. It preserves the unresolved architectural boundary between registered bounded recipes and the original guide's prohibition on inventing a new graph query language; it does not approve arbitrary Cypher as a shortcut.