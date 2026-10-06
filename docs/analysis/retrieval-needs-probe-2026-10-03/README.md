---
title: 'Standalone retrieval-needs step: implementation and evaluation'
description: 'Historical analysis and saved observations for Standalone retrieval-needs
  step: implementation and evaluation.'
type: explanation
status: draft
created: '2026-10-03'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# Standalone retrieval-needs step: implementation and evaluation

The isolated step is implemented and **17 deterministic tests pass**. It places all information-need questions in one Jev request inside a single LangGraph node. It is not connected to production retrieval.

**The approved live evaluation completed: 7 of 12 cases passed all frozen checks.** All twelve received valid responses from `jev-1.13.0`, with exactly one HTTP request and response per case, no retries and no chunking. Each request held 34-36 independent classification questions. The five failing cases expose semantic decisions to improve before integration; none was hidden by changing expectations or thresholds.

Worktree: `typed-research-binding-v01`; branch: `experiment/retrieval-needs-single-call`; base: `2d4bee9fe665bc2f9b173baa752081bde69bc34c`. The new source files and the expected results are pinned in the [approved-run manifest](../../../reports/retrieval-needs-probe-2026-10-03-live-approved/freeze.json). Their fingerprints match the original prelive freeze.

## What this step does

1. Receive the original question, bounded supplied context, observed ID candidates, a finite schema catalog and unchanged source scope.
2. Build independent classification questions for entity types, target IDs, requested fields, document types and relationships. Each option can be selected independently; multiple IDs or document types can survive together.
3. Include finite choices for detail level, completeness, hierarchy inclusion and whether scope is clear, needs source discovery, or lacks a user choice. Include an explicit check for information the catalog cannot represent.
4. Send the whole batch once, with no retry or chunk fallback. The first prepared case contains **35 classification questions in one request**, not 35 model calls. The local limit of 128 is a bound, not evidence that the provider supports every possible batch size.
5. Retain the raw distributions. Probabilities at least 0.7 are selected, at most 0.3 rejected, and intermediate options remain uncertain. Validate essential gaps without inventing IDs or fields.
6. Return the proposed need and unresolved dimensions. `decided` means ready for later retrieval; it does not mean answered. `needs_resolution` does not itself dispatch a human question. The unchanged original question remains available for later checks.

No source retrieval, database access, query generation, final answer, source-completeness assertion or Langfuse export occurs here.

## The concrete exact-AC example

**Input:** “For KM-500c-2, what must tests demonstrate?”

The request offers bounded repository concepts such as acceptance criteria, source code, test definitions, ADRs and schemas. It includes the literal `KM-500c-2` as a candidate and no actual repository excerpts. Expectations were written by the test agent and enriched by an independent PO/BA/ITPO reviewer **before model results**. The actual column below comes from the approved live response.

| Dimension | Independent expectation | Actual live result |
|---|---|---|
| Entity type | Acceptance criterion | Acceptance criterion |
| Target IDs | `KM-500c-2` | `KM-500c-2` |
| Required information | Canonical criteria; test specification is an acceptable additional field when recorded | Criteria, test specification, declared test links, content and provenance |
| Detail | Specific fields or the bounded full criterion | Specific fields (0.97) |
| Document type | Canonical AC definition | Canonical AC definition |
| Parent/child relationships | None required | None selected |
| Completeness | Complete requested information for this one entity | Single entity (1.0) |
| Hierarchy population | Not applicable; no counting clarification | Not applicable (0.77) |
| Scope | Ready for a later exact lookup | Sufficient (0.95), `decided`, no unresolved dimensions |

Uncertainty was retained rather than converted into required work: test entity type; `work_status`, lifecycle status, level, parent, mapping and compatibility fields; and immediate parents, direct children and linked-test relationships. These were not selected and did not force clarification. The extra selected test links/content show that a pass on the essential checks does not prove minimum field selection.

The [actual local receipt](../../../reports/retrieval-needs-probe-2026-10-03-live-approved/N01.receipt.json) contains the complete wire request and actual response: **one HTTP request, 35 classifications, model `jev-1.13.0`, request `req_01a100c429737a8fb0d34356321d6500`**. The [expected-versus-actual result](../../../reports/retrieval-needs-probe-2026-10-03-live-approved/N01.result.json) passes the frozen checks. This fixes the interpretation for this probe; it does not prove the later database lookup or answer works.

## Enriched evaluation set

The [frozen twelve-case set](eval-cases.json) reuses the prior scenario and persona catalogs, adding boundary cases and explicit forbidden shortcuts. Required labels and acceptable alternatives are stored separately from model input and are never sent to Jev. Every original `RS-01` through `RS-29` has a planning applicability or downstream-only disposition in that file; none is claimed as a full retrieval pass.

| Case | What the question exercises | Frozen verdict and observed result |
|---|---|---|
| N01 | Exact AC's test requirements | **Pass:** literal ID, canonical criteria, no population gate |
| N02 | Count test-writing ACs, exclude parents | **Pass with unresolved dimensions:** exact count, exclude all parents, source discovery, no invented TQ root; detail mode and catalog coverage remain uncertain |
| N03 | Count L2/L3 descendants of TQ-500f by work status | **Fail:** correct ID/fields/all-descendants/root exclusion, but detail mode confidence splits between fields (0.58) and bounded context (0.40), so plan remains unresolved |
| N04 | Follow `work_status` through code | **Fail:** identifies source code and field mapping, but calls completeness single-entity (0.70), incorrectly requiring a target ID |
| N05 | Full AC with its immediate parent | **Fail:** selects correct ID, parent and bounded context; hierarchy inclusion falls to unknown because include-root is 0.68. Node otherwise reports decided |
| N06 | Compare two named ACs | **Pass:** both IDs retained and complete selected-entity comparison |
| N07 | Show lifecycle and implementation statuses | **Pass:** both distinct fields selected |
| N08 | Find criteria about missing research inputs | **Fail:** criteria/source discovery correct, but examples (0.52) vs exhaustive set (0.32) leaves completeness unresolved; hierarchy also below threshold |
| N09 | Exact AC with conflicting prior context | **Pass:** user's literal target wins over the context recommendation |
| N10 | Payroll question outside this catalog | **Pass:** unmet catalog information declared, no unrelated entity/document types selected |
| N11 | Quoted prompt injection in context | **Pass:** original target and source scope retained; injected target not selected |
| N12 | Governing ADRs and contracts | **Fail:** selects ADR and schema entity types, but schema document type is uncertain (0.68), leaving only ADR documents selected |

No model result has been used to relax an expectation. The [full readable result report](../../../reports/retrieval-needs-probe-2026-10-03-live-approved/results.md) gives every selected and uncertain dimension, exact question, expected-versus-actual mismatch and per-case receipt link. The [machine-readable summary](../../../reports/retrieval-needs-probe-2026-10-03-live-approved/summary.json) records 12 attempts, 12 responses, 7 passes and 0 invalid runs. N02's expected result deliberately permits unresolved ambiguity; its pass is not a fully specified count plan or population proof. N07 also selected criteria and test specification beyond the two requested status fields. Extra fields were not comprehensively forbidden by the frozen gold, so the 7/12 score measures essential predicates, not optimal minimum retrieval.

These results suggest three follow-ups, none implemented here: distinguish independent facts such as field projection and surrounding context instead of forcing overlapping choices; model code/dataflow completeness without requiring a named entity; and check consistency between chosen entity types and required document types. N05 shows that nonapplicable hierarchy ambiguity can affect the strict score without blocking useful parent retrieval. Thresholds stayed at the frozen values throughout; there was no post-result prompt tuning or second attempt.

## What the local tests establish

The [17 tests](../../../tests/kernel/retrieval/test_retrieval_needs_probe.py) exercise the actual node and existing adapter, using a controlled transport and the real HTTP transport backed by a local HTTP mock. They verify one actual HTTP POST containing all questions, no retries, pre-send overflow refusal, malformed-response rejection, retained uncertainty, immutable question/scope, multiple selections and meaningful exact-ID/parent-context boundaries.

The original test run was RED because the agreed module did not yet exist. After implementation, the suite passed in 0.63 seconds. Two plausible wrong versions were tested in memory and rejected: silently accepting an uncertain named target, and collapsing multiple targets to the first. Source was not mutated by those checks. See the [deterministic proof record](../../../reports/retrieval-needs-probe-2026-10-03/deterministic-proof.json).

The step still expresses topic membership and explicitly allowed levels such as L2/L3 partly through the unchanged original question. Its catalog is an experimental semantic catalog, not a guarantee of current graph fields or endpoints. An all-descendants need remains distinct from a later execution depth cap. These are integration questions to resolve after measuring this step's actual Jev decisions.

Before the successful run, one sandbox network attempt failed with `ConnectError` and zero responses; automatic approval then rejected the expanded payload. The user subsequently explicitly approved all twelve cases. The approved run used a separate output directory and freeze. The [earlier infrastructure record](../../../reports/retrieval-needs-probe-2026-10-03/N01.result.json) remains intact and is not included in semantic quality scoring. Total across both runs: 13 HTTP request events, 12 responses, 12 evaluated cases; processing or billing of the failed connection is not asserted. No extra model calls, retries, graph writes or Langfuse exports occurred.
