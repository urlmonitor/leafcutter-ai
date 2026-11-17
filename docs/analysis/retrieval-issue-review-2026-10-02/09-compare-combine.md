---
title: 'Issue 09: Compare actual attempts, combine evidence, rank and assess'
description: 'Historical analysis and saved observations for Issue 09: Compare actual
  attempts, combine evidence, rank and assess.'
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# Issue 09: Compare actual attempts, combine evidence, rank and assess

Analysis only; code verified at `887c66d3896ba7727ce41b743887210a3883c6ce`. Scope: S5 / RS-17-20. Read both CLAUDE files, research-agent/test-writer/IT-PO guidance, the completion-gap analysis, target journey and sibling 04/05 contracts. No implementation, AC changes, tests, providers or hosted writes.

## Finding and evidence boundary

Extend the existing research LangGraph after attributable child collection. Compare actual attempts **before** combining; preserve complementary evidence independently of preference. Ranking cannot establish factual completeness.

The graph-only lane in `reports/retrieval-scenarios-2026-10-02-retest-887c66d3/results.md` reports zero answers: RS-02/03 stopped upstream at population clarification. RS-17/18 were not run. RS-19 has a correct direct missing-field facet; RS-20 a correct direct 15-record, 5-done/10-todo facet. Three separately partial continuation pages do not establish an aggregate answer. These receipts do not exercise comparative target behavior.

The later `default-source/results.md` records native evidence followed by real `synthesize_evidence` waits for both questions, with no executed host response or final answer. RS-03 cites committed evaluation/oracle/catalog documents rather than canonical `KM-500c-2.yaml`. This confirms native ranking/assessment reachability, not independent answer correctness or a multi-method comparison.

The target `docs/product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json` remains `realization: spec`, `readiness: draft`. Its compare -> remember -> combine -> rank -> assess sequence is proposed, not delivered.

## Verified current mechanisms and gaps

| Symbol / source | Verified behavior and implication |
|---|---|
| `kernel/capabilities/retrieval/rerank.py::rerank`, `_judge`, `_enough` | Bounded Jev relevance over native candidates, lexical fallback under data policy, explicit-locator retention and early stopping. This ranks snippets for a need; it does not compare query/search/traversal executions. |
| `knowledge/capability_fit.py::assess_capability_fit` | Classifies pinned source kinds/relationships/fields and missing-operation eligibility before build. Capability fit is not observed retrieval usefulness. |
| `kernel/capabilities/research/executor.py::build_research_graph`, `_collect`, `_evaluate` | Current graph is plan/collect/evaluate/finish. Collection merges before Jev assessment; no shared pre-combination attempt comparison exists here. |
| `research/collect.py::_absorb_bundle`, `_absorb_child` | Keeps useful bundles, failures as limitations, contradictions and truncation. Evidence dictionary uses `stronger_category`; source IDs cannot substitute for method receipts. |
| `kernel/contracts/evidence.py::Evidence`, `Provenance`, `stronger_category` | Evidence ID hashes locator/content; one provenance object carries producer/invocation/strategy. Repeated identical IDs keep the existing item, except category promotion: multiple supporting attempts are not unioned. Native locator identity alone does not necessarily include revision. |
| `research/state.py::Collected.merge_coverage`; `research/assessments.py::merge_assessments/guard_assessments` | Strongest coverage wins, but conflicting conditional reports are preserved and unresolved reports force partial. Useful safeguards; neither preserves arbitrary conflicting field values nor validates original-answer obligations. |
| `research/collect.py::judge`, `apply_answers`, `thin_coverage` | Jev checks conflict/evaluability and currently satisfied needs; per-need checks only downgrade. No method winner is selected. |
| `knowledge/answers.py::assess_answer`, `_limitations`; `knowledge/answer_models.py::AnswerAssessment` | Deterministic required-field, revision, scope, incomplete-enumeration and unknown-status checks exist. Semantic/hybrid relevance and continuation pages cannot establish an exact population. |
| `integrations/knowledge_capability.py::to_kernel_evidence`; `knowledge_execution.py::_answer_diagnostics` | Structured field values/citations are dropped by the mapping; actual answer assessment is diagnostic-only. Sibling 04 owns repairing their transport. |

**Source-inferred risk, not a reproduced incident:** a satisfied native sibling can dominate graph partial coverage while field obligations are absent from the collector. First-provenance retention also loses an alternative method's support. The current conditional-report guard does not close either general seam.

## Options

| Option | Tradeoff |
|---|---|
| Reuse native rerank unchanged over flattened results | Small, but destroys method attribution before comparison and confuses relevance with completeness; insufficient. |
| Add explicit nodes to existing research graph | Reuses kernel lifecycle, continuation, budgets and child artifacts. Additive contract work is necessary. **Recommended.** |
| Introduce a separate comparison orchestrator/store | Clear isolation, but duplicates state, resume and budget authority; unnecessary for this issue. |

## Contract and smallest staged extension

Consume sibling 05's persisted `AttemptEnvelope` and sibling 04's immutable original-question/answer packet. Do not execute returned children again. Each comparison snapshots attempt/output references, obligation version, source pins and limits; a later changed result needs a new snapshot.

**Stage A:** retain one actual attempt and all support paths through restart; report usefulness without a comparative winner. Expose a separate `unassessed` outcome when judgment is unavailable. **Stage B:** compare two actual results, including partial/failed siblings, before combination. **Stage C:** rank the combined set and invoke the shared final-answer assessment; add no retry loop here.

Proposed nodes, with exactly one owner each:

| Node | Owner and output |
|---|---|
| `prepare_comparison` | System: validate receipts/authority and build compatibility groups plus bounded evidence views. |
| `compare_attempts` | Jev: bounded observed preference, tie, complementary, no-useful or incomparable choice; selected attempt/evidence IDs and reason codes. |
| `validate_comparison` | System: enforce offered IDs, snapshot binding, compatibility and single-attempt/null-winner rules. |
| `record_advice` | System, S7 implementation: accept comparison event and return record reference or storage limitation before combination. |
| `combine_evidence` | System: build canonical groups, support lists, conflict records and retained limitations. |
| `rank_combined` | Jev: bounded relevance judgments over offered combined IDs against original question. |
| `apply_order_and_bounds` | System: validate ordering, retain unranked items explicitly, apply disclosure bounds and recompute hard obligations. |
| Shared `judge_answer` | Jev, sibling 04: semantic adequacy over the checked answer packet. |
| Shared `guard_and_return` | System: enforce hard gates; emit answer/assessment handoff for S6 routing. |

No free-text Jev authorship is required: use existing bounded Choice/noul mechanisms and deterministic reason rendering. Stable sorting implements accepted relevance judgments. Score thresholds from different retrieval methods are not directly comparable.

A proposed `ComparisonAssessment` carries snapshot ID, attempt IDs, comparison groups/reasons, outcome, nullable preferred attempt, retained evidence IDs with contribution/obligation references, judgment provenance, and limits. Preference and complementarity are independent: preferring A must still allow B's unique necessary fact. A tie permits useful evidence; no-useful differs from unavailable/unassessed. No winner may name an untried method.

System compatibility checks bind the same original question and obligation version, authorized repository/revision/generation, canonical field meaning, population root/levels/inclusion/relation/depth and applicable limits. Different field subsets may complement the same obligations; different populations cannot silently become one denominator. Cross-revision questions retain distinct revision partitions. Unequal budgets/disclosure or source conditions are explicit confounders: conditional usefulness may be reported, never causal or universal method superiority.

Deduplicate in two layers: immutable evidence artifacts remain intact; aggregate identity uses repository + canonical kind/ID + source version. Keep generation/mapper identity and disclosure provenance on every support record. For native chunks use verified source identity/version and span/hash; map to canonical entities only with an established mapping. Exact duplicates collapse display, while overlapping excerpts retain their ranges and citations. Similar text is not entity equivalence.

For every entity/field retain all observed values, availability, locators, attempt IDs and evidence references. Preserve source role, authority and derivation: an analysis document quoting a canonical clause remains attributed analysis until the canonical source is inspected; repetition across derivative documents is not independent corroboration. Identical values union support; disagreeing values become explicit alternatives/conflicts, never last-writer-wins. An unavailable field from A can be answered by B's compatible actual value without erasing A's limitation. Required conflicts remain unresolved unless an explicit authority rule resolves them with attribution.

Keep useful partial evidence beside empty success, outage, denial and unknown outcomes. A waiting attempt is unfinished, never empty or failed. Combining subsets proves only known unique membership unless the enumeration owner supplies a validated complete same-scope aggregate. After final ranking/clipping, recheck required fields, exact clauses, source authority and completeness. High Jev confidence cannot waive these gates.

## Existing AC disposition

All listed ACs are active/approved; these are verified work statuses, not target completion.

| Exact AC | Work status | Required treatment |
|---|---|---|
| KM-500c-2 | done | Preserve actual source/unsatisfied needs and separate build/query/answer outcomes. Add pre-combination actual-attempt comparison and explicit winner/tie/complementary/none/incomparable clauses. |
| KM-500c-3 | done | Reuse bounded stopping; S6 owns changed-plan policy. Add retained comparison/evidence on budget stop and resume. |
| KM-500e-2 | in_progress | Complete canonical fields/citations; extend multiple-support and conflicting-value preservation through final output. |
| KM-500e-3 | in_progress | Complete distinct-identity/unknown-status/15-versus-11 population contract after combination and final bounds. |
| KM-500e-4 | in_progress | Preserve gap distinctions; capability fit cannot stand in for observed comparison. |
| KM-400d-5 | done | Reuse stable evidence/retrieval identity and explicit stale permission; add cross-method support union without hiding freshness. |
| KM-500f-1/2/3/4/5 | in_progress | Preserve relation scope, execution/deployment distinctions, stated ranking policy, inspected-source limits and discriminating proof. These do not establish generic method comparison. |

A focused new subordinate AC must cover comparison outcomes, compatible grouping, support-preserving dedup and bounded ranking. Allocate IDs later through BA/IT-PO; this report changes no criteria/status.

## RED and negative proof

Use real retrieval/disclosure serializers and adapters into the real collector/public KernelService; controlled Jev isolates wiring. Independent oracle: pinned source bytes and reviewed population membership, never the merge helper's output. Capture behavioral RED before coding; no tests ran here.

1. Same question: real query plus native result reach comparison separately before combine. Assert one-attempt/null winner, tie, complementary, no-useful and incomparable controls. Reject foreign attempt/evidence IDs and stale snapshots.
2. Two producers return one entity/version through different paths: one counted member, both supports survive serialization/restart. Swap arrival order. Mutants: first-provenance wins, count paths, text-similarity dedup.
3. Same field has conflicting actual values; retain both and prevent fulfillment. Twin: disjoint compatible fields complete obligations. Wrong repository, revision, generation or 11-leaf/15-descendant scope cannot silently merge. A quoted oracle/analysis passage cannot acquire canonical authority through dedup.
4. Partial useful A plus timed-out B retains A and B's outage; empty successful B stays distinguishable. All-unavailable produces no-useful-data, not verified absence.
5. Optimistic Jev with missing work_status, clipped clause, contradictory field or partial pages stays partial. Complete single-response oracle returns 15/5/10; aggregate positivity requires genuine enumeration proof.
6. Ranking cannot discard the sole required fact and retain fulfilled status. Exhaust comparison/ranking budget, deny excerpt transmission, replay receipts and restart: preserve useful evidence, explicit unassessed limits and unchanged counters.

S1 owns receipts/replay/accounting; search/traversal own results/completeness; 04 owns final answer transport. S6 receives unmet obligations, conflicts, comparison and retained evidence references, but owns retries/clarification. S7 receives observed comparison with final fulfillment pending, later linked assessment separately; storage failure must not block the answer or rerun retrieval. The evaluation owner defines contamination/holdout policy. Live semantic quality remains a later independently authorized evaluation.
