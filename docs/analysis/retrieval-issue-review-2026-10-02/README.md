---
title: Retrieval issue review — 2026-10-02
description: Historical analysis and saved observations for Retrieval issue review
  — 2026-10-02.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# Retrieval issue review — 2026-10-02

Fourteen independent issue analyses, consolidated after the fresh retest. **No complete target journey passed.** Typed research routing progressed; answer delivery remains unfinished. Recommendations below are proposed integration design, not implemented changes, new ACs or sign-offs.

## What the retest establishes

Evaluated code and default native bytes: `887c66d3896ba7727ce41b743887210a3883c6ce`. Graph source: `59269e024e4d0290b68b03d0d382745966e67e29`, mapper **7**, semantic readiness **false**. A code merge did not republish that graph.

| Evidence lane | Observed outcome | Boundary |
|---|---|---|
| [Graph-only canary](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/results.md) | Two starts, eight Jev calls; research entered, then population clarification; zero answers. | Exact-ID RS-03 receives irrelevant count scope. RS-02 needs clarification, but gets duplicated technical wording. |
| [Actual default sources](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/default-source/results.md) | Two starts, ten calls; native evidence, then `waiting_host/synthesize_evidence`; zero answers. | Fifteen sources, backend `none`; no host executed. This is a supported handoff, not Neo4j proof. |
| Direct service controls | Eight active facets correct; pagination and terminal-leaf checks correct. | Lower-layer evidence, not completed research journeys. Historical 4/12 concerns an older projection. |
| [Aggregate](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/aggregate.json) | **Four starts, two distinct questions, 18/24 calls, zero final answers/full passes.** | **27/29 full journeys unrun.** Unused allowance is not a new execution authorization. |

Default RS-03 cites committed evaluation/oracle material without canonical `KM-500c-2.yaml`; that is not independent answer-quality proof. Saved host excerpts were omitted under explicit `telemetry_excerpts=none`; unchanged default `truncated` behavior was **not tested**. No host execution means omission cannot explain an observed synthesis failure. Pagination receipts remain valid despite the helper's later exit-1 serialization error.

## Issue index and next proof

ACs identify existing obligations; `done` records do not establish these expanded journeys. Exact statuses and source anchors are in each report and the [canonical AC store](../../acceptance-criteria/knowledge-management/). Numbers in dependency entries refer to reports here. All listed proofs remain proposed unless explicitly identified as retest observations above.

| Issue and actual gap | Main alternatives and recommendation | ACs / dependencies | Specific next proof |
|---|---|---|---|
| [02 Exact ID](02-exact-id.md): population gate blocks; source inspection also finds exact catalog/mode/input-role gaps. | Extend existing registered-query path; separate exact branch or generic binding redesign are larger alternatives. | KM-500a-2, KM-500e-1/2; 03/04. | Question-only RS-03 returns the canonical clause; distinguish linked-test question, absent ID and wrong kind. |
| [03 Clarification](03-clarification.md): technical duplicated prompt; prose decoder treats ordinary replies as component IDs. | Persist focused choices and validated prose patches; wording-only repair is insufficient. | KM-500a-1, KM-500e-1; 04. | Ordinary-language reply resumes the same run after restart, preserves scope/budget and avoids repeated questions. |
| [04 Answer contract](04-answer-contract.md): original question, structured fields and answer assessment do not reach the root as one contract. | Extend existing typed bundle/collector; prompt-only repair or a separate composer cannot close that seam. | KM-500c-2, KM-500e-1/2/3/4; 02/03. | Positive root answer plus optimistic-Jev negative with missing fields and a satisfied native sibling. |
| [05 Method attempts](05-method-attempts.md): source history is not durable comparative method history. | Extend research continuation: one attempt, then two selected methods; reject a separate ledger/orchestrator. | KM-500a-2, KM-500c-2/3; 04/15. | Completed A survives restart while B waits/fails; one receipt/charge, strict required need preserved. |
| [06 LLM preparation](06-llm-preparation.md): no typed argument/term generation or model-profile receipt. | Two narrow host operations preferred; closed union viable; unattended provider adapter later. | KM-500a-1/2; 02/04/05 and new preparation clauses. | Caller terms bypass generation; five valid suggestions survive real host packet/resume; wrong binding executes nothing. |
| [07 Search](07-search-portfolio.md): native ranking exists; portfolio/readiness contract missing; vectors unready. | Native keyword attempt first; approved Decision vectors later; general document vectors require broader scope. | KM-400c-2/3/4/5, KM-500d-4; 05/06/09. | Useful keyword evidence survives vector timeout; unready methods are excluded; retain separate outcomes. |
| [08 Traversal](08-traversal.md): fixed reads exist; adaptive frontier/visited/resume loop absent. | Add graph then immutable folder traversal within existing research; more recipes alone cannot satisfy navigation. | KM-400d-3/4, KM-500e-3, KM-500f-1; 05/09/10. | A–B–A cycle plus unseen C survives restart; non-reading choices bypass read/judgment; escape and byte limits hold. |
| [09 Compare/combine](09-compare-combine.md): collection merges before comparison and can lose support paths. | Explicit existing-graph nodes; flattened reranking or a separate comparison store is insufficient. | KM-500c-2, KM-500e-2/3; 04/05. | Compare two actual outputs before combining; retain conflicting values and both provenance paths after dedup/restart. |
| [10 Fallback](10-fallback.md): no shared assessed route to a changed method/frontier. | Bounded existing-graph routing; increasing retries or always synthesizing cannot supply missing facts. | KM-500c-3, KM-500e-4; 03/04/05/08/09. | One changed alternative succeeds; identical retry refused; exhaustion exposes retained partial root output. |
| [11 Learning](11-learning.md): approved decisions exist; automatically discoverable retrieval advice does not. | Distinct advisory family under `kernel.memory`; neither fake approved decisions nor another strategy database. | KM-500d-3, KM-500g-1/2; 04/05/09/10. | Automatic admission is found in a fresh process; Jev may reject it; storage failure preserves the answer. |
| [12 Query growth](12-query-growth.md): bounded authoring exists; actual author, compatibility and lifecycle proof incomplete. | Finish recipe path; ordinary registered-code delivery for unsupported operators; defer arbitrary Cypher. | KM-500b-4/5, KM-500e-4; 04/05/06. | Real actor authors candidate; independent expectations reject irrelevant recipes; fresh process executes admitted digest. |
| [13 Freshness](13-source-freshness.md): older graph observed; actual canonical-event publication unproven. | Existing main sync plus exact manual replay and durable receipts; scheduled reconciliation only if needed. | KM-500d-2; source policy, 04/05. | Actual event-to-serving readback with SHA/generation correlation; stale policy, privileges and capacity verified separately. |
| [14 Evaluation/observation](14-evaluation-observation.md): no finished canary; benchmark leakage and operational/telemetry coupling. | Finish narrow clean canaries, then representative benchmark; remote tracing is a separate lane. | KM-500a-4, KM-500d-3, KM-500g-1/2; 02/03/04. | Real terminal answers with independent canonical oracle; operational packet round-trip under every telemetry policy. |
| [15 Typing](15-typing.md): informational receipt has 175 errors/42 imported files; no comparable fresh baseline. | Pin baseline, repair boundaries in batches; temporary identity ratchet possible; defer wholesale strictness. | KM-400e-3, KM-500b-3; consume 04/05/09 models. | Same toolchain/roots base-versus-candidate; preserve truncation, optional answers, serialization and lifecycle behavior. |

## Proposed delivery order and ownership

1. Establish reproducible typing/evaluation baselines (15/14) alongside behavioral RED for 02–04. Repair exact targeting and clarification, then complete structured root answers. Optional prose follows that positive path.
2. Prove one durable attempt (05), then two outcomes and comparison (09), followed by one bounded changed-method return (10). Add native search (07), preparation (06) and traversal (08) against these contracts.
3. Complete query-growth lifecycle (12), automatic advisory reuse (11) and publication operations (13) in their own scopes. Publication and embeddings are separate. Broaden evaluation (14) only after finished canaries.

One shared 05 selection authority consumes 07's eligible offers. 04 owns the original obligations/answer packet; 03 supplies validated clarification patches. 06 owns preparation handoffs; 09 compares actual attempts; 10 returns changed plans to 05. Each LangGraph node has one runtime owner; kernel continuation, dispatch and cumulative budgets remain authoritative.

Integration decisions still needed: precise shared schemas, accepted search-set versus variant semantics, ambiguous I/O crash policy, and 12's bounded-recipe versus general authoring boundary. **Five suggestions do not mandate five calls.** Automatic advisory publication is distinct from human-approved `DecisionRecord` authority. Operational content protection must be separate from optional telemetry projection.

Never merge lifecycle `status` with `work_status`, execution with fulfillment, or the pinned **15 root-excluded descendants (5/10)** with **11 terminal leaves (4/7)**. A partial walk/page cannot prove completeness. Mixed-source coverage override is a source-inferred risk, not a reproduced live incident.

## Validation note

Reviewed all 14 reports against retest receipts and pinned HEAD; all 59 Markdown links resolve, UTF-8 decodes strictly, and no control characters were found. All 48 explicit AC IDs resolve; checked work-status claims match canonical YAML. PO/BA/ITPO/research templates informed value, testability, interface and evidence review; no authoring/sign-off workflow ran.

Minimal corrections: 04's stale copied-prompt warning now reflects corrected summary metadata; 06's two-start statement explicitly names the graph-only lane. Analyst recommendations, runtime/AC files and historical/raw receipts were untouched. Recommended implementation work and future proof remain proposed. Validation used packaging/source checks only; no test suites or providers were invoked.
