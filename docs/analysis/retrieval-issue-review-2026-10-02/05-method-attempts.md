---
title: 'S1: Durable method attempts and bounded method selection'
description: 'Historical analysis and saved observations for S1: Durable method attempts
  and bounded method selection.'
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# S1: Durable method attempts and bounded method selection

Analysis only, 2026-10-02. Inspected code: `887c66d3896ba7727ce41b743887210a3883c6ce`. No production code, AC, provider, publication or PR changes.

**Recommendation:** extend the existing research continuation and kernel child lifecycle with a typed, attributable method-attempt record. First preserve one actual result through a restart; then permit a bounded ordered selection of two offered methods. Keep LangGraph nodes explicit and the existing kernel authoritative for dispatch, waits, identity and budgets.

## Observed boundary versus target gap

The new RS-02 and RS-03 receipts in `reports/retrieval-scenarios-2026-10-02-retest-887c66d3/` both reach research and stop at `waiting_human`, asking for population choices. They return no answer/evidence. RS-03 is the exact-ID question "For KM-500c-2, what must tests demonstrate?" This is an upstream answer-contract/clarification defect, not observed failure of a multi-method dispatcher. The receipts pin data revision `59269e024e4d0290b68b03d0d382745966e67e29`, distinct from inspected code.

The old completion-gap analysis identifies S1 as missing. Source inspection supports that architectural gap, but it cannot establish that fixing S1 alone repairs these two stops. The target flow `docs/product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json` is `realization: spec`, `readiness: draft`: its `offer-methods -> plan -> retrieve -> compare` contract is a design hypothesis. It explicitly permits multiple selected children without promising parallel execution.

## Current mechanisms and precise seams

| Evidence (repository-relative source and symbol) | What exists; what S1 must add |
|---|---|
| `integrations/query_graph.py:132` `_select`; `:153` `_execute`; `:190` `build_query_growth_graph` | One `picked: str` selects an operation; execution ends at END. Ending the method child is correct. Its parent needs an attributable return contract, rather than re-executing the query for comparison. |
| `integrations/query_growth.py:73` `_select`; `integrations/query_planning.py:33` `choose` | At most 50 graph-capable descriptors, one Jev Choice, membership and confidence checks. No cross-method offer or multiple-selection contract. `get_entities` is excluded by the graph filter; exact-ID catalog repair is a separate prerequisite. |
| `knowledge/query_models.py:66` `QueryDescriptor`; `knowledge/query_catalog.py:120` `builtin_descriptors` | Stable operation/version/digest, purpose, question examples, typed parameters and result meaning are useful offer building blocks. They are not a generic search/traversal contract. |
| `integrations/query_growth.py:44` `_initial`; `:146` `_execute`; `:186` `_continued` | Source/generation pin, answer obligations, selected query diagnostics, current-wait schema checks and matching activation receipt exist. `original_question` starts from the child need's question, which may already contain a category prefix; preserve the root question separately. |
| `kernel/capabilities/research/planning.py:213` `_child`, `:250` `_children`, `:308` `resolve_sources` | Actual code uses `EvidenceNeed`, not a separate `ResearchNeed` model. Each need can already produce graph and native children. This is source grouping, not Jev choosing alternative methods. Keep need identity and method-attempt identity separate. |
| `kernel/capabilities/research/state.py:38` `ResearchContinuation`; `results.py:45` `waiting_result`; `executor.py:139` `_evaluate` | Needs, source map, attempted sources, evidence, coverage, deferred host children and synthesis waits persist in the owning work item. `attempted: list[str]` contains source IDs, not actual method receipts. Add method records here; do not create a second orchestration store. |
| `kernel/contracts/work.py:35` `RequestBody`, `:84` `Continuation`, `:113` `ChildOutcome`; `kernel/scheduler/merge.py:165` `plan_proposals`, `:340` `_settle_waiting` | Kernel assigns child identities, links matching existing requests and records current wait IDs. A resumed parent receives result references, including prior terminal children. Use those references and a consumed-receipt set. |
| `kernel/scheduler/guards.py:157` `request_dedup_key` | Dedup hashes canonical payload, need and revision; generic `id` fields are dropped. A newly salted `attempt_id`, timestamp or refreshed limit in payload could defeat dedup. Persist an immutable execution payload; never rebuild it on resume with a new ID. |
| `kernel/scheduler/merge.py:321` `_settle_terminal` | COMPLETED parent is blocked by a failed REQUIRED child. `_child` currently copies need priority. A REQUIRED evidence need and an optional alternative method are different obligations; model alternatives as SUPPORTING children while keeping required need coverage strict. Mandatory authority/admission waits inside a method remain required. |
| `kernel/capabilities/research/planning.py:94` `afford_needs`; `kernel/scheduler/nodes_execute.py:43` `ShareBudget`; `nodes_integrate.py:117` `integrate` | Existing Jev/work-item shares, reserve, time/cost accounting and guard counters must remain authoritative. `afford_needs` assumes one retrieval child per need, whereas `_children` can emit two. Size costs from actual selected children and judgment calls before dispatch. |
| `kernel/scheduler/state.py:110` `Budgets`; `knowledge/contracts.py:84` `RetrievalBudget`; `integrations/knowledge_execution.py:178` | Run counters cover calls, work, retries, cost and time; neutral retrieval also bounds candidates, rounds and bytes. No inspected run-wide counter aggregates all those retrieval dimensions across distinct methods. Any new cumulative dimension belongs in the existing kernel budget authority; an attempt's usage copy is audit data, not spend authority. |
| `integrations/knowledge_execution.py:279` `_assess_final_answer`, `:297` `_answer_diagnostics`, `:315` `_kernel_result`; `integrations/knowledge_assessment.py:89` `assessment_bundle` | Actual `result.answer` is currently diagnostics `knowledge_answer`; bundle `assessments` transports the different `result.assessment` conditional-proof packet. S1 must carry typed answer assessment separately from conditional proof and execution status, using the answer-contract owner's schema. |

## Design alternatives

| Option | Benefit | Cost / decision |
|---|---|---|
| Add a list/loop directly inside query-growth | Small local change for several registered queries. | Query-specific scope, graph restriction and local call stack become a poor owner for search/traversal, host waits and collection. Avoid as the portfolio owner; keep it a query-method child. |
| Extend research's continuation and existing child requests | Reuses source restrictions, kernel waits/dedup, shared budget and result artifacts. Single method can land before multiple methods. | Requires an additive typed contract and explicit collect/dispatch nodes. Recommended. |
| New portfolio service with its own ledger/worker/checkpointer | Isolates a new subsystem. | Duplicates kernel lifecycle, budget and recovery authority; introduces reconciliation and two owners. Reject for S1. |

## Proposed contract and node ownership

These are proposed names and shapes, not existing APIs or assigned AC IDs.

1. **System `offer_methods`:** emit an immutable `MethodOfferSnapshot`: `offer_id: str`, `question_ref: str`, `obligations_ref: str`, `scope_ref: str`, `source_pins: list[SourcePin]`, `remaining_budget_view`, `selection_cap: int`, `methods: list[MethodContract]`, `unavailable: list[reason]`. A contract names `method_id/version/digest`, executor binding, supported need/result meaning, input/output schemas, preparation actions, source requirements and enforceable bounds. Resolve availability/permissions before offering. Missing vectors or endpoints remain explicit unavailable facts; query build is conditional capability repair, not a generic method.
2. **Jev `choose_method`:** select only an offered method/action ID, using the original question, immutable answer obligations, prior attempts and bounded criteria. Reuse literal Choice questions. For multiple selection, choose up to two slots without replacement; the next slot includes `stop_selection`. Avoid inventing a multi-select provider API or enumerating an exponential powerset. Every call consumes the existing budget. Low confidence has an explicit clarification/insufficient-evidence outcome.
3. **System `validate_selection`:** enforce offer digest, membership, unique selections, cap, mutually compatible pins/permissions, required inputs and total affordability. Reject stale/foreign/over-cap selections; do not silently choose another method. Zero selected methods is legal only with an explicit supported stop/clarify/gap action. Known explicit registered-operation bypass remains deterministic under KM-500a-2; the normal question route's Jev selection is a separate contract.
4. **System `dispatch_selected`:** retain the frozen selection and emit the next existing `RequestProposal`. Start sequentially: pending selected methods remain in `ResearchContinuation`; waiting returns through the kernel. No new worker pool. Internal query clarification/build/admission and future preparation reuse normal typed host/human waits. A wait is not a failed/empty terminal attempt.
5. **System `collect_attempt`:** resolve the child's actual result artifact, validate correlation and append its receipt once. Preserve failed and empty outcomes beside useful evidence, then dispatch the next affordable selected method or pass the collection to comparison. No query/search/traversal is executed by collection.
6. **Jev comparison owner (S5):** consumes the collection. S1 returns attributable facts; it does not select a winner, combine evidence, infer relevance or decide retry policy.

Proposed `AttemptEnvelope` (stored in the research continuation and final typed bundle/artifact, with bounded reference lists):

| Fields | Contract |
|---|---|
| `attempt_id: str`, `run_id: str`, `parent_work_item_id: str`, `need_id: str`, `execution_key: str` | One logical method attempt. Kernel work-item/invocation retries are distinct receipts beneath it, not new chosen methods. Derive stable identity from run/parent and canonical method execution identity; do not salt it per resume. |
| `offer_id: str`, `selection_ref: str`, `method_id/version/digest: str`, `operation_id/version/digest: str|null` | Attributable offered/accepted choice; operation fields nullable for non-query methods. Preserve Jev template/model and selection record references. |
| `original_question: str`, `question_ref: str`, `focused_need_question: str`, `answer_requirements_ref: str` | Exact root question survives child targeting; clarified obligations are versioned extensions, not silent replacement or removal of required facts. |
| `source_pins: list[SourcePin]`, `scope_ref: str`, `permissions_ref: str`, `input: object`, `input_origins: object` | Bound query args/terms/locators and their known/generated/clarified origins. Source pins retain repository, revision/generation and mapper or content identity. Recheck authority before dispatch; do not widen it after a wait. |
| `state: selected|waiting|terminal`, `terminal_status: completed|partial|failed|blocked|null`, `result_kind: nonempty|empty|unavailable|error|null` | Lifecycle, execution outcome and evidence presence are independent. Empty requires successful inspected output; a timeout is not zero matches. |
| `child_work_item_id: str|null`, `receipt_refs: list[str]`, `output_schema_id: str|null`, `output_ref: str|null`, `evidence_refs: list[str]` | Before dispatch IDs may be absent; terminal acceptance requires matching persisted child/result receipts, not caller assertions. Record aliases when kernel dedup links an existing child. |
| `coverage: object|null`, `answer_assessment: typed|null`, `conditional_assessment: typed|null`, `limits: list[str]`, `usage_refs: list[str]` | Carry actual producer assessments and observed usage separately. Null is unknown. Completed execution never implies complete population or fulfilled answer. Cumulative budget remains kernel-owned. |

Alternative-child priority must not downgrade the evidence obligation. Distinguish substitutable attempts for the same fact from complementary methods serving separate mandatory facts; do not blanket-convert required dependencies to SUPPORTING. If all alternatives fail or remain incomplete, the REQUIRED need stays unsatisfied and an all_required research result cannot complete. A best_effort envelope may complete under existing policy only while exposing the unsatisfied need; it never upgrades its coverage. Typed need/answer assessment remains decisive.

Dedup depends on canonical executable meaning, including method/query version, typed inputs, source pins and frozen bounds. Reporting metadata must not create a fresh executable request. A changed plan is a new logical attempt only after the retry-policy owner authorizes the change; an identical selection links the prior receipt. Preserve per-attempt evidence references even when the normal evidence store deduplicates content.

## Recovery and budget acceptance boundary

"Exactly once" needs a precise meaning. Existing kernel dedup proves useful logical behavior: an equivalent completed child is linked, and its result can be consumed once. `tests/kernel/scheduler/test_merge.py:121` already targets that behavior. `test_checkpoint_restart.py:61` uses a fresh graph/connection and real SQLite to test host pause/resume, but does not prove a query backend executes once through an arbitrary crash.

`nodes_execute.py:147` awaits external execution before producing a checkpointable result; `nodes_integrate.py:105` stores the result artifact afterward. A crash after external I/O but before a durable receipt has an ambiguous outcome. Do not claim physical exactly-once I/O from an AttemptEnvelope. For strict at-most-once dispatch, add a durable started/unknown marker through the existing kernel authority and refuse blind replay of unknown work; this may lose availability. True exactly-once external execution additionally needs a backend idempotency/receipt protocol. This is an explicit AC caveat, not a reason to create another ledger.

For committed receipts: no redispatch on repeated delivery, clarification, collection or restart; consume usage once and retain prior evidence. Resume uses the same pinned execution payload. For in-flight uncertainty: record unknown outcome and potentially consumed allowance conservatively; do not restore a fresh budget. Any new candidate/read/byte totals extend existing kernel accounting and are charged from validated receipts, with unknown usage visible. Size the selected plan from emitted children, mandatory internal work and reserved comparison/final assessment; do not count needs as methods.

## Smallest staged change and dependencies

- **Stage A: one attributable attempt.** After upstream exact-ID/clarification fixes, add the envelope/receipt projection for current registered-query and native retrieval results. Persist through existing waits; expose typed answer assessment with the answer-contract fix. Route the parent back to existing evaluation without a new comparison algorithm. Add strict serializer/schema registration and old-continuation compatibility.
- **Stage B: bounded two-method selection.** Add System offer/validation and Jev slot selection in research; dispatch sequentially, preserving completed attempts while the next method waits or fails. Mark substitutable method children SUPPORTING while required need coverage remains enforced. Test public kernel reachability and budgets before adding search/traversal internals.
- **Stage C: shared return interface.** Pass `{original_question, requirements, pins, attempts, remaining_budget_view}` to S5. S5 returns references to actual attempts/evidence and a separate judgment. S6 consumes that judgment and proposes a bounded changed plan; System validates it before S1 dispatch. Neither S5 nor S6 rewrites receipts or owns counters.

S2 preparation consumes a frozen method/version/input schema and returns a typed validated input proposal plus provenance; it cannot grant source facts or permissions. S3/search and S4/traversal consume the same scoped execution request and emit actual results, coverage, limits and usage. Traversal owns its frontier/visited payload; S1 retains its reference across waits. Query growth keeps its matching admission receipt. Advisory memory is downstream and cannot be a prerequisite for returning retrieved evidence.

## AC mapping: actual statuses and missing clauses

All listed ACs are `status: active`, `req_status: active`, `readiness: approved` in the inspected store. Work status below is not a claim of whole target completion.

| Exact AC | work_status | S1 treatment / gap |
|---|---|---|
| KM-500a-2 | done | Preserve typed query selection and deterministic explicit bypass. Extend for offered method contracts, bounded one/multiple choice and selection-to-attempt correlation. Current singular query contract does not establish a portfolio. |
| KM-500c-2 | done | Preserve separation of build, query and answer outcomes. Extend to per-method envelopes and typed transport into shared assessment, without confusing conditional proof with answer fulfillment. |
| KM-500c-3 | done | Preserve bounded attempts and no budget reset. Extend duplicate/committed-receipt/restart guarantees to method children; specify ambiguous external-I/O crash semantics. S6 owns progress/retry choices. |
| KM-500e-1 | in_progress | Dependency: preserve original question and resolved answer obligations across child targeting, selection and resume. The fresh observed clarification stops belong here/upstream. |
| KM-500c-1 | done | Reuse matching query activation receipt and original-need resume; do not duplicate admission authority. |
| KM-500a-1 | done | Reuse human waits while retaining frozen offers, prior attempts and remaining budgets. Ordinary-language clarification repair is owned separately. |
| KM-500e-2, KM-500e-3 | in_progress | Dependencies: canonical facts and complete-population requirements remain binding even when an execution completes. |
| KM-500e-4 | in_progress | Offer/build eligibility must distinguish missing input/query/source facts; absent offers do not prove no answer. |
| KM-500a-4 | todo | Eventual real Jev selection quality proof. Local scripted decisions only prove wiring, not live semantic quality. |
| KM-500g-2 | in_progress | Receipts must bind diagnoses to actual method, request, source revision and observed result. |

No existing AC explicitly covers all of: common method envelope; capped multiple selections; per-attempt return to comparison; failure of one alternative preserving another; committed receipt reuse across restart; cross-method retrieval-budget accounting. Add focused clauses/new child ACs through later BA/IT-PO work; do not mark these covered merely because the above ACs are done. IDs are deliberately unassigned in this analysis.

## Required RED and negative evidence

Use actual public kernel orchestration and adapter-produced outputs with local fixture sources. Reuse the SQLite restart harness and current merge/research tests; no provider calls are needed to prove these seams. RED means a behavioral assertion fails for the intended missing contract before implementation, not import errors or source grep. Independent test-writer ownership follows the current template; no tests were authored or executed in this analysis.

| Test boundary | Required assertion / wrong version to kill |
|---|---|
| Zero / one / two / cap+1 | One selected method produces one attributable receipt; two produce distinct receipts and collection. Explicit stop produces none. Unknown, repeated, foreign-version and over-cap selections cause zero unauthorized calls. Kill "always run all methods" and silent fallback. |
| Root question and authority | Exact original question survives prefixed needs, changed input preparation and waits. Wrong repo/revision/generation/permission/offer digest is rejected. Kill replacing root question with category text and scope widening. |
| Empty / partial / failed / useful sibling | Actual empty success, clipped useful output and timeout retain distinct outcomes. One failed optional method cannot erase the useful sibling or satisfy the required need by itself. Also assert all-failed and all-incomplete alternatives leave the REQUIRED need unsatisfied, while missing complementary mandatory facts prevent all_required completion. Kill blanket parent failure, failure-as-empty and SUPPORTING-as-sufficient. |
| Answer contract transport | Actual neutral `result.answer` survives mapping/collection/restart separately from conditional `result.assessment`. A positive method status or Jev vote cannot upgrade a partial population. Kill the present diagnostics-only transport. |
| Duplicate delivery and linked work | Deliver the same receipt twice and propose equivalent work twice; observe one logical attempt/output and one charge, with no extra adapter invocation. A deliberate new query version/input remains distinguishable. Kill random identity salts and double usage integration. |
| Restart at waits and completed receipt | Close the SQLite connection; construct new service/runtime; resume after method A completes while B awaits input. A is not called again; B retains pins; collected receipt and counters match uninterrupted control. |
| Crash boundary | Inject failure before dispatch, after adapter return and after durable result. After committed result, never rerun. For ambiguous I/O, produce the agreed unknown/refusal outcome or prove backend idempotency; never label absence of a receipt "not executed". |
| Budget conservation | A consumes calls/bytes/candidates, B waits and resumes; remaining allowance is cumulative, reserves survive and next work stops at the boundary. Kill fresh `RetrievalBudget()` per method and one-child-per-need cost assumptions. |
| End-to-end reachability | Start a typed ordinary research request, obtain a real method result and observe collection/evaluation consuming it. Fail if new helpers exist but the public route still goes directly to an unannotated result. |

Reviewed guidance: `.claude/CLAUDE.md`, root `CLAUDE.md`, `templates/agents/research-agent.md`, `templates/agents/test-writer.md`, `templates/agents/it-po.md`, and ADR-053. Their relevant disciplines are source-backed findings, independent behavioral RED evidence, explicit producer/consumer contracts, and deterministic authority checks versus Jev semantic choice. This analysis does not invoke the broad planning/enrichment workflow or create sign-offs.
