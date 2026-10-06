---
title: Independent review of the standalone retrieval-needs step
description: Contract, source and frozen-request review before expanded live evaluation.
type: explanation
status: draft
created: '2026-10-03'
last_updated: '2026-10-03'
components: [knowledge_management, decision_kernel]
---
# Independent review

Reviewed against the [predeclared acceptance contract](acceptance-contract.md) and [independently enriched evaluation set](eval-cases.json). Base `2d4bee9fe665bc2f9b173baa752081bde69bc34c`, branch `experiment/retrieval-needs-single-call`. This review is limited to the experiment; it does not sign off full retrieval, change an AC status or authorize provider exports.

## What the source establishes

- The isolated graph is `START -> determine_needs -> END`. Existing production registries, research flows, global provider configuration, database code and host synthesis are unchanged. Only new experiment modules/tests/runner use the entrypoint.
- Every entity kind, offered target ID, required field, document type and relationship receives an independent probability. Detail, completeness, hierarchy inclusion and scope resolution use finite choices in the same shared batch. Nothing waits for another field decision before asking its question.
- The existing TypeSafe adapter is configured with zero retries. The batch rejects question overflow before transport; `_SingleSend` rejects a second transport invocation and mismatched returned question IDs. Direct HTTP transport has one POST and no internal retry. Bounds are local to the experiment.
- The original question is preserved. Supplied IDs are candidates; literal IDs are extracted without fabricating a target. Scope is retained without becoming access permission. Catalogs describe semantic needs, not merely current Neo4j capabilities.
- Outcomes retain selected, rejected and uncertain options plus the full validated provider distributions. An unsupported catalog remains unresolved with the original meaning intact. `decided` means a proposed information need, not an answered question.

## Findings resolved before live evaluation

1. Generic uncertainty and unsupported categories initially became `needs_clarification`. The result now uses `needs_resolution`; this step does not automatically ask a human.
2. Exact-entity needs could initially be considered decided despite no selected ID or document type. These missing essentials now remain unresolved, while thematic discovery can legitimately have no ID.
3. Two selected items require both named targets unless an explicit relationship identifies an additional item for discovery. A request for an AC and its immediate parent therefore does not require the caller to know the parent ID.
4. Requested all-descendant scope remains distinct from the proposed execution depth bound. Parent exclusion differs from excluding only a root; full selected-item context is bounded.
5. Scope resolution separates enough information to begin retrieval, source discovery, a genuinely missing user choice and uncertainty. Unknown facts alone do not force user clarification.

No remaining source-review blocker was identified for trying the isolated step. This is not a claim that Jev will choose the correct fields; the frozen semantic evaluation is intended to measure that.

## Frozen-request checks

Read-only verification of the first saved [request/response receipt](../../../reports/retrieval-needs-probe-2026-10-03/N01.receipt.json) confirmed:

- At the time of the read-only check, the dataset and all four code/runner hashes matched [freeze.json](../../../reports/retrieval-needs-probe-2026-10-03/freeze.json).
- The single prepared request contains 35 classification questions and exactly these state sections: original question, context, source scope, offers and instructions.
- Actual HTTP request-event body equals the prepared wire body. Expected labels, human gold and grading assertions are not included in that body. The local receipt omits authorization headers; the inspected question/context/catalog contains no credentials.
- There is one HTTP request event and zero response events. The attempt failed at the connection boundary. It supplies no Jev semantic outcome; a request event alone does not prove provider receipt or billing.

After that failed attempt, the test writer corrected only the report renderer to distinguish a send attempt from a received provider response. The earlier receipt and freeze are preserved; a newly authorized run must use a new output directory and fresh runner hash. The three experiment modules and evaluation expectations remain unchanged.

## Deterministic verification

The independent test writer recorded [17 passing tests in 0.63 seconds](../../../reports/retrieval-needs-probe-2026-10-03/deterministic-proof.json), including the actual HTTP transport with a local mock, single-request/no-retry behavior, exact and multiple targets, an immediate parent discovered by relationship, malformed responses, bounded payloads and unresolved dimensions. Two behavioral mutants were caught: silently accepting an uncertain required target and collapsing two selected targets into one. The initial missing-module failure is scaffolding evidence only, not a behavioral RED test. These checks use controlled responses and establish no live semantic quality.

Expanded live evaluation is pending permission after automatic approval review rejected transfer of the expanded twelve-case payload under the earlier two-question authorization. No alternative provider call, smaller hidden payload or fallback was used by this reviewer.

## Remaining boundaries

The twelve expectations were reviewed before live output, including exact IDs, ambiguous versus explicit count scope, code flow, bounded parent context, two-target comparison, distinct status fields, broad discovery, conflicting context, unsupported payroll meaning, instruction injection and multiple document types. All 29 original scenarios have planning-only applicability labels; none is a downstream retrieval pass.

Explicit level filters and topic membership are not yet a complete typed population contract beyond the retained question and scope decision. Context and source metadata are caller-supplied, not independently verified evidence. The finite catalog can expose unsupported meaning but does not generate a new field schema. Model thresholds are experimental. No query selection, context collection, retrieval, enumeration, clarification/resume, answer fulfillment or learning is proven here. These are integration boundaries, not reasons to conceal or replace an observed semantic failure.
## Approved live evaluation addendum

The user subsequently explicitly approved the twelve-case TypeSafe evaluation. The preceding pending-permission paragraph is historical. The test writer executed the frozen set once in [a separate approved-run directory](../../../reports/retrieval-needs-probe-2026-10-03-live-approved/results.md). This reviewer then inspected the actual receipts and distributions; no prompt, threshold, case expectation or probe source was changed and no additional request was made by this reviewer.

**Verified result: 12 valid responses; 7/12 pass the predeclared predicates; 5/12 fail.** Every case has exactly one recorded HTTP request and one HTTP 200 response, with 34-36 independent classifications in that request. All returned `jev-1.13.0`. These are semantic experiment outcomes, not retrieval answers. The earlier connection failure remains separately recorded and does not affect these twelve semantic scores.

### Evidence integrity

Read-only comparison confirmed the current dataset hash and all three probe-module hashes equal both the original pre-output freeze and the approved-run freeze; base commit is unchanged. Each saved expected file exactly matches its frozen case. Each actual sent request body equals its saved prepared wire body. Expected predicates and human gold are absent from all twelve wire bodies. Authorization headers are not recorded. The runner's previously disclosed reporting-only correction is pinned in the new freeze. There were no invalid schema/provider runs, retries, chunk fallbacks or unrecorded repeat cases in this approved run.

### Exact question: what came back

For **"For KM-500c-2, what must tests demonstrate?"**, [N01](../../../reports/retrieval-needs-probe-2026-10-03-live-approved/N01.result.json) returned:

| Dimension | Actual decision |
|---|---|
| Entity | Acceptance criterion (`ac`). Test entity remains uncertain. |
| Target | `KM-500c-2`, probability 0.82. |
| Required fields | `criteria` 0.84, `test_spec` 0.83, `covered_by` 0.76, `content` 0.82, `provenance` 0.77. |
| Document type | Canonical AC definition (`ac_yaml`). |
| Relationships | None selected. Immediate parent, direct children and linked tests remain uncertain; they are not mandatory retrieval steps. |
| Detail | Specific fields, 0.97. |
| Completeness | One entity's requested information, 1.00. |
| Hierarchy inclusion | Not applicable, 0.77. |
| Scope | Sufficient to begin retrieval, 0.95. |
| Outcome | `decided`, no unresolved dimensions; one request, no population clarification. |

Other field alternatives, including work status, lifecycle status, level, parent, mapping and compatibility, remain explicitly uncertain. They were not selected. This meets the frozen exact-AC predicates, including retaining the literal ID and avoiding a population requirement. It does not retrieve the criterion or fix the production graph path.

The pass is not proof of a minimal information request. `covered_by` is an extra declared-test-link field beyond the canonical behavior clause needed by this question. The status-only question N07 also selected criteria and test specifications in addition to the requested status fields. The frozen grader permits these extras; they are a qualitative over-selection concern, not a retroactively changed failure score. A future consumer must not treat every useful supporting field as an indispensable answer obligation.

### The five failed cases

| Case | Actual failure | Interpretation and narrow proposed next step |
|---|---|---|
| N03: explicit descendant count | Correct target, work status, level, all-descendants, root exclusion and exhaustive count; detail raw choice `fields` 0.58 versus `bounded_context` 0.40 becomes unknown and blocks readiness. | Detail/content extent overlaps relation needs. Make those dimensions orthogonal and define readiness only for answer-relevant unresolved decisions; do not lower the threshold to erase this result. |
| N04: code field flow | Selects source code and mapping, but completeness `single_entity` 0.70 conflicts with discovery 0.81 and absent IDs; result asks to resolve target IDs. | Material interpretation error. Distinguish one conceptual field's path from one identified repository entity; preserve ID-free discovery for a code path. |
| N05: AC plus immediate parent | Correct literal target, immediate-parent relation and bounded context 0.95. Hierarchy raw choice `include_root` 0.68 versus `not_applicable` 0.31 becomes unknown, though status stays decided. | Bookkeeping uncertainty, not an observed wrong traversal. Make population inclusion explicitly inapplicable to selected-item context, or represent selected items separately from count population. Frozen failure remains. |
| N08: find existing missing-input criteria | Correct AC, criteria and discovery. Completeness `examples` 0.52 versus `exhaustive_set` 0.32 and hierarchy not-applicable 0.68 become unknown. | Label/readiness ambiguity. Distinguish positive evidence sufficient to show a specification exists from exhaustive coverage required to claim none exists; avoid unrelated hierarchy uncertainty obstructing discovery. |
| N12: governing ADRs and contracts | Schema entity 0.77 is selected, schema document type 0.68 is merely uncertain; only ADR documents selected, yet status is decided. | Material missing-source risk if a consumer drops uncertainty. Add a deterministic cross-dimension consistency check that retains the unresolved schema source; clarify the offered contract/document distinction without inventing a source choice. |

N02 passes its deliberately permissive ambiguous-count expectations: no invented TQ-500 root, exhaustive count, exclude parents and discovery. It is still unresolved because detail `fields` 0.66 falls below the selection threshold and outside-catalog probability 0.40 is uncertain; no required fields were selected. Therefore it is an honest unresolved case, not a ready count plan.

### Review recommendation

The experiment establishes that one physical Jev request can independently assess the requested dimensions and correctly handle the exact AC, two literal IDs, separate statuses, conflicting context, an unsupported topic and the synthetic instruction-injection case under these predicates. Seven passes are not seven complete retrieval journeys, and the twelve cases are not a general reliability estimate.

Before integration, tighten the meaning of detail versus relationships, conceptual subject versus canonical target, and required versus useful supporting fields. Add a prospective held-out test for unnecessary required fields and a consistency test for selected entity types with uncertain necessary source types. Keep current receipts and frozen grading unchanged. These are proposed follow-ups only; this review did not implement, tune or rerun them.