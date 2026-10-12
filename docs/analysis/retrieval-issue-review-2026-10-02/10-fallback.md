---
title: 'Issue 10: Bounded fallback after insufficient evidence'
description: 'Historical analysis and saved observations for Issue 10: Bounded fallback
  after insufficient evidence.'
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# Issue 10: Bounded fallback after insufficient evidence

Analysis only, 2026-10-02; code verified at `887c66d3896ba7727ce41b743887210a3883c6ce`. Scope: S6 / RS-10, RS-16, RS-25-27. Only this report was written. No tests, production/AC edits, providers, hosted writes or planning workflow ran. Reviewed root/.claude guidance, research-agent/test-writer/IT-PO prompts and ADR-053; applied source evidence, discriminating consumer tests, precise contracts and single-owner decisions.

## Finding and evidence boundary

**Extend the existing research continuation with an assessment-to-permitted-action route.** Reuse sibling 05's method attempts, sibling 09's comparison and sibling 04's answer contract. A failed method is neither an empty answer nor a failed evidence need when another permitted method supplies the required facts. A method change never relaxes the need.

The fresh graph-only retest reports zero answers: RS-02/03 stop at population clarification before query execution. The later `reports/retrieval-scenarios-2026-10-02-retest-887c66d3/default-source/results.md` reaches native evidence and `waiting_host/synthesize_evidence`; no host response, retry or resume was executed. Neither lane proves fallback. The target `docs/product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json` is draft/spec: assess-to-plan/clarify/stop remains proposed.

## Verified current mechanisms

| Source and symbol | Current behavior; missing contract |
|---|---|
| `kernel/capabilities/research/executor.py::build_research_graph`, `_evaluate`, `_after_collect` | Four nodes: plan/collect/evaluate/finish. Thin evidence can release deferred host children or request synthesis. Synthesis resume finishes without rejudgment. No shared changed-method/frontier route. |
| `research/state.py::ResearchContinuation`; `results.py::waiting_result` | Needs, source attempts, evidence, coverage and limits persist in the existing work item. Synthesis explicitly snapshots collected state; any new wait must retain the complete accepted packet too. Source IDs are not method receipts. |
| `research/collect.py::collect_outcomes`, `_absorb_child` | Prior evidence merges with children; failed/blocked children become limitations, never empty bundles. Failure detail is coarse here, so typed cause/attempt references must survive the S1 handoff. |
| `research/planning.py::_child`; `kernel/scheduler/merge.py::_settle_terminal` | Child priority copies need priority; a failed REQUIRED child blocks a COMPLETED parent even after another alternative succeeds. Reuse S1's SUPPORTING substitutable attempts, strict REQUIRED evidence obligations, and unchanged mandatory admission/authority dependencies. |
| `scheduler/guards.py::retry_allowed`; `merge.py::_settle_failed` | Existing retryable errors retry the same work item/binding within `max_retries`. This is transport recovery, not semantic method selection. Never create a fresh child to reset its retries. |
| `guards.py::request_dedup_key`, `attempt_fingerprint`; `nodes_integrate.py::_no_progress` | Canonical request dedup and WAITING fingerprints exist. Fingerprints use request, global evidence and version fields, not changed frontier identity. Legitimate empty expansions could hit the same fingerprint; arbitrary `_version` increments could evade it. Extend this same guard with validated progress identity, not a second guard loop. |
| `integrations/query_planning.py::clarification`; `query_growth.py::_resume` | Bounded human waits and matching current-wait/schema checks exist. Clarification count is child-continuation local: new method children must not refresh the overall allowance. |
| `scheduler/state.py::Budgets`; `nodes_execute.py::ShareBudget`; `nodes_integrate.py::integrate` | Existing kernel owns shared work/call/retry/time/cost accounting. S1/S4 add missing cumulative retrieval dimensions here; fallback consumes remaining allowance, never creates a ledger. |
| `nodes_lifecycle.py::decide_outcome`; `kernel/service_envelope.py::_visible_output` | Guard stops can classify useful global evidence as partial, but visible output requires an actual validated partial root bundle. Global evidence IDs alone do not provide an attributable partial answer. |

## Options

| Option | Tradeoff |
|---|---|
| Increase retries or always synthesize | Small but repeats ineffective work; prose cannot supply missing source facts. Insufficient. |
| Add bounded routing nodes to existing research graph | Reuses waits, artifacts, budgets and recovery; requires typed state and producer/consumer proof. Recommended. |
| New fallback orchestrator/checkpointer | Isolated control but duplicates lifecycle, authority and accounting. Reject. |

## Smallest staged design

**Stage A:** retain actual attempts and a validated partial answer at every return/wait boundary; finish or stop honestly without new methods. **Stage B:** allow one genuinely changed permitted alternative through S1, then recollect/reassess once. **Stage C:** add observed traversal continuation and post-evidence clarification using S4/03 contracts. Bounds remain configurable and cumulative; no unbounded `while insufficient` loop.

Proposed nodes extend the same LangGraph; names are not existing APIs:

| Node | Sole owner and handoff |
|---|---|
| `offer_return_actions` | System: from checked answer/comparison, current permissions, available methods/frontier and remaining budget, offer immutable actions with explicit unavailable reasons. |
| `choose_return_action` | Jev: bounded choice among finish, changed method/inputs, observed frontier, focused clarification, partial or stop. No invented operation, question prose or source. |
| `validate_return_action` | System: validate membership, snapshot/pins, obligation compatibility, meaningful change, retry eligibility and spend before dispatch. Reject invalid choice explicitly. |
| `retain_and_route` | System: checkpoint accepted evidence/attempts/decision; use S1 dispatch, S4 frontier or existing human wait; terminal branches assemble the checked result. |
| Existing clarification answer | Human: supply missing intent/policy or an explicit authority decision. |
| `validate_clarification_resume` | System: consume only matching current reply once; apply accepted patch within authorized scope; return to offered planning with retained evidence and remaining limits. |

Use the existing semantic answer judgment, not another sufficiency vote here. If decision budget is unavailable, System returns retained evidence as unassessed/partial. Optional wording stays with sibling 04; retry/clarify/stop never requires prose generation.

Proposed `ReturnDecision` contains `snapshot_id: str`, `assessment_ref: str`, `action: enum`, `selected_offer_id: str|null`, `change_basis: enum|null`, `reason_code: str`. Snapshot references original question/obligation version, need IDs, comparison and `AttemptEnvelope` receipts, retained evidence/conflicts, source pins, traversal frontier and authoritative budget view. Continuation adds pending decision/wait and consumed receipt references; usage copies remain audit data only.

A meaningful change is a different permitted method, validated new effective input, observed unvisited frontier, or matching verified capability activation. Rewording, timestamps, fresh attempt IDs, higher confidence or renewed allowance are not change. Keep transient same-operation retries exclusively in existing scheduler policy, with attributable retryable cause and remaining allowance; permanent denial, unsupported mapping and empty success cannot request that retry. A changed input must address the diagnosed gap; it cannot silently widen scope or switch revision. Human intent patches retain the original question and earlier obligation versions; incompatible earlier facts remain attributable, not silently repurposed.

Keep outcome distinctions: successful empty, partial/insufficient, unavailable/outage, denied, unsupported mapping, stale, exhausted, cancelled, unknown execution and missing capability. Only verified absence of a suitable operation over supported data enters existing governed build. No useful eligible route yields explicit stop; useful retained evidence yields partial with unmet needs and cause. Neither establishes global absence. Failed alternatives remain recorded even when the final need is satisfied.

Apply kernel limits before dispatch and during bounded method work, including assessment reserve. Clarification/restart does not replenish calls, method attempts, bytes, candidates, depth, retries or active time; existing human-wait time treatment remains. On hard scheduler exhaustion before research finalization, extend the existing terminal assembly path to expose a validated retained root partial packet without new reads or judgment. Preserve cancellation status; do not force success to reveal evidence.

## AC disposition

All below are active/approved. Status is recorded work status, not proof of the target journey; no changes made. IDs resolve under `docs/acceptance-criteria/knowledge-management/`.

| AC | Work status | Required disposition |
|---|---|---|
| KM-500a-1 | done | Extend post-evidence focused clarification, same-run retained findings and shared clarification allowance. |
| KM-500a-3; KM-400e-4 | done | Reuse distinct empty/outage/denied/exhausted/unsupported outcomes through fallback; add sibling-success route. |
| KM-500c-1 | done | Reuse matching activation/resume identity; generalize attributable delivery to S1 methods, never treat activation as evidence. |
| KM-500c-2 | done | Extend assessed return decisions while preserving original obligations and strict required coverage. |
| KM-500c-3 | done | Extend unchanged-loop prevention to changed-method/frontier routing, retained partial output and cumulative budgets across restart. |
| KM-400d-3; KM-400d-4 | done | Reuse scoped continuation and session limits; integrate method/navigation dimensions under kernel authority. |
| KM-500e-4; KM-500g-2 | in_progress | Complete cause-specific next action bound to matching attempt/revision; no guessed outage diagnosis or fabricated build opportunity. |
| KM-500f-2; KM-500f-3 | in_progress | RS-27 proof inventory stays partial; RS-26 asks missing policy after retaining facts, never invents it. |

Allocate any focused child ACs later through the normal authoring owner. Existing done clauses and tests do not establish the expanded target.

## Discriminating RED and restart proof

Capture behavioral RED before implementation via real `KernelService`, serializers, adapters, collector and SQLite reopen; controlled Jev proves wiring, not live decision quality. No tests ran here.

1. **RS-10/25:** A returns useful facts, B fails. Preserve A and B's typed cause; alternative C satisfies the same REQUIRED need and completes. Twin: all alternatives fail, required need remains unsatisfied. Kill required-attempt blocking, priority downgrading of needs and all-or-nothing collection.
2. **RS-16:** bounded traversal dead end offers a genuinely different method or unseen C frontier; its actual result returns through comparison. Reject identical operations, reworded inputs, changed timestamps/IDs/version salts and A-B-A cycles. An empty expansion with real frontier progress remains eligible within bounds.
3. **RS-26:** evidence first, missing ranking policy second. Pause, close process, answer and resume the same run. Assert original question, source pins, facts, attempts, accepted policy and conserved counters. Reject stale/foreign/conflicting/duplicate replies; never re-ask resolved inputs or rerun committed reads.
4. **RS-27:** independently exhaust calls, work, retry, active-time and retrieval limits before dispatch, after collection and before root finalization. Useful root partial output includes unmet facts and stop cause; no extra provider/read occurs. Kill fresh per-method budgets and child-local clarification reset.
5. **Transient versus permanent:** bounded retryable outage succeeds once within the same item's allowance; denial/unsupported/empty never triggers unchanged retry/build. Repeated outage stops with the correct cause and retained sibling evidence.
6. **Crash/replay:** interrupt before dispatch, after I/O and after durable receipt. Completed receipts are consumed once; ambiguous I/O follows S1's unknown/idempotency policy. Replay cannot spend twice, erase failures, activate unverified code or fabricate answer fulfillment.

Reuse existing research, query-growth adversarial, scheduler guard/checkpoint and interaction restart test homes. Dependencies: 03 clarification, 04 answer/partial packet, 05 attempts/dispatch, 08 frontier, 09 comparison. S6 owns only the checked return route; S7 advisory-write failure must not rerun retrieval. Independent live fallback evaluation remains unperformed.