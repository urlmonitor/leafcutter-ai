---
title: Independent source review of the LLM retrieval-needs experiment
description: Trust-boundary findings, corrections and limits before blind interpretation outputs.
type: explanation
status: draft
created: '2026-10-03'
last_updated: '2026-10-03'
components: [knowledge_management, decision_kernel]
---
# Independent source review

Source review is green for the isolated host interpretation experiment. The initial source review preceded blind LLM outputs; the final outcome addendum below records the completed comparison. It does not approve production activation, classifier promotion or retrieval integration.

The new [typed contracts](../../../kernel/contracts/retrieval_needs.py), [host operation](../../../kernel/capabilities/host/retrieval_needs.py) and [experiment harness](../../../integrations/retrieval_needs_llm.py) use the existing KernelService, LangGraph scheduler, persisted host packet/input artifact, submission ledger and resume flow. The shared submission hook is empty for other operations. The new request/output schema pair is registered and exported; the operation has no default capability descriptor. The ephemeral descriptor identifies an experimental harness and ADR-053, not a classifier-quality approval.

## Findings resolved before evaluation

- Explicit host `needs_resolution` with neither an explicit reason nor a structural gap previously became `decided`. It now fails semantic validation before ledger acceptance. Structural unknowns remain unresolved without requiring a duplicated free-text reason.
- Adding structural gaps to 32 existing unresolved reasons previously bypassed the output schema through `model_copy`. Projected overflow now fails before acceptance, and conversion revalidates its normalized output.
- Host usage accepts an arbitrary model identifier, while this output bounds it to 200 characters. Normalization now catches invalid metadata and returns a deterministic failed result instead of raising after ledger acceptance.
- New schema exports and catalog valid/invalid fixtures were required. Both exports and four fixture directories are present; catalog expectations now include 18 schemas.
- The evaluation freeze now includes all changed runtime/schema plumbing and the base commit, rather than only the four new files.

Membership checks bind selected and uncertain labels to the pending request, reject overlap and reject question/scope changes. Context and known IDs are candidates, not permission. The echoed `source_scope` is caller metadata; actual kernel Scope/permissions remain separate. No retrieval is performed, so the echo is not evidence that a repository path or revision was checked.

## Evaluation integrity and remaining limits

I independently rechecked SHA256: the original twelve-case gold and all three original Jev probe modules still match the first freeze. The original 7/12 Jev result is unchanged. The [comparison contract](../retrieval-needs-llm-2026-10-03/evaluation-contract.json) was reviewed before new outputs: shared semantic predicates remain equivalent, unsupported needs use an explicit unresolved marker instead of fabricated probabilities, and the prospective minimality overlay is reported separately for both engines.

The controller prepares real host packets and referenced inputs. The blind worker must receive only those artifacts, without gold labels, earlier outputs or repository enrichment. One accepted host operation and zero Jev calls establish kernel transport behavior; they do not establish one underlying LLM request or known token usage. Reported model provenance comes from host submission usage and remains unknown when absent.

This is an exploratory comparison on the same twelve cases, with the new prompt informed by earlier failures. It cannot establish held-out accuracy, complete source coverage, final-answer correctness or an approved automatic fallback policy. Method selection, query execution, semantic fallback activation and the generic classifier evaluation/admission lifecycle remain outside this implementation. No AC status changed.

See the [contract and architecture note](contract-and-architecture.md) for the existing classifier/approval facilities and partial AC mapping. The test owner retains deterministic RED/GREEN evidence. The separate outcome review follows.


## Final independent outcome review

The isolated kernel lifecycle works. The LLM interpretation is not yet reliable enough to treat `decided` as proof that the required information has been fully identified. I independently checked saved raw responses, accepted result records, the unchanged expectations and the [acceptance proof](../../../reports/retrieval-needs-llm-2026-10-03-accepted/acceptance-proof.json).

| Measure | Observed result |
|---|---|
| Accepted kernel submissions / completed interpretations | 12 / 12; one durable accepted submission per run |
| Jev calls during the LLM trial | 0 |
| Frozen shared semantic checks | LLM 8/12; saved Jev baseline 7/12 |
| Separate prospective minimality/consistency overlay | LLM 7/7 applicable cases; saved Jev 1/7 |
| Model identity, underlying requests and tokens | Unknown; submission usage was empty |
| Retrieval, final answers and automatic fallback activation | Not performed |

Acceptance is established by the durable ledger copies matching the original blind responses and completed runs, not by the `host_operations` usage counter: that counter records issued host waits. I verified the ledger/response hashes in the supplemental proof, matching run and interaction IDs, unchanged payloads, completed envelopes and zero Jev calls for all twelve cases.

### What the LLM actually returned

For [N01](../../../reports/retrieval-needs-llm-2026-10-03-accepted/N01.result.json), the question was: **For KM-500c-2, what must tests demonstrate?**

| Dimension | Actual interpretation |
|---|---|
| Entity and target | `ac`, `KM-500c-2` |
| Required fields | `test_spec` only |
| Documents | `ac_yaml` |
| Relationships | None |
| Detail and completeness | `fields`, `single_entity` |
| Hierarchy and scope | `not_applicable`, `sufficient` |
| Status and uncertainty | `decided`; no unresolved or uncertain values |

The frozen contract requires `criteria` when projecting fields for this question. The model assumed that `test_spec` alone supplies the obligations; no source was retrieved to substantiate that assumption. N09 and N11 repeat this omission while correctly preserving the literal target against conflicting context and quoted injection. These three failures are one recurring field-selection problem, not three different routing failures.

[N10](../../../reports/retrieval-needs-llm-2026-10-03-accepted/N10.result.json) correctly selected no unrelated entities or fields and retained `needs_resolution` for unsupported payroll information. Its unresolved item was `needs_outside_catalog: Employee identities, payroll amounts ...` rather than the exact standalone `needs_outside_catalog` marker. This fails the frozen serialization expectation while preserving the unsupported meaning. The score remains a failure; it must not be reported as an invented payroll answer or silently regraded.

All five cases that failed the earlier Jev predicates now pass: N03 retains all descendants, root-only exclusion, levels and work status; N04 discovers the code/contract flow without demanding an ID; N05 keeps exactly the immediate parent; N08 discovers relevant criteria; N12 includes both ADR and schema sources. N02 also has a usable discovery interpretation without treating the candidate TQ-500 family as the requested population. The detailed [results](../../../reports/retrieval-needs-llm-2026-10-03-accepted/results.md) retain every case and expected/observed difference. Passing minimality checks does not compensate for missing mandatory information.

### Integrity and disclosed controller repairs

I rechecked the successful freeze against current runtime files, original gold and prospective overlay. The earlier three Jev modules and original gold still match their first freeze. All twelve operational inputs preserve the original question, supplied context, known IDs, the four non-ID catalog descriptions and the same derived target-ID sets. Generated ID descriptions are equivalent paraphrases across engines, not byte-identical provider prompts. Enrichment is explicitly disabled with no evidence, consulted sources or scanned files.

The initial prepare failure removed only an old nested catalog `schema_version` property before the successful new freeze; no option mapping or question changed. The first submission wrapper used a slash-containing actor ID, which the existing Actor schema rejected for all twelve waits before acceptance. The [wrapper repair record](../../../reports/retrieval-needs-llm-2026-10-03-accepted/wrapper-repair.json) preserves those rejected attempts and documents the same actor encoded as `codex:root:needs_llm_host`. The corrected submissions resumed the existing waits. Raw responses and operational input copies are byte-identical across the repair; no model rerun or semantic edit occurred.

The test owner reports 76 deterministic tests plus 82 subtests passed, including all 18 new controlled cases. The existing query-build fixture repair adds missing mappings and a valid response; the security change adds query-build to existing authority-forgery negatives. I inspected those diffs: they do not weaken checks or modify production behavior. The additional security run passed 9 tests plus 27 subtests. These deterministic fixtures establish mechanics, not LLM accuracy.

### Bounded follow-up recommendations

1. Clarify the relation between canonical requirement clauses and test specifications in the information-needs contract. For obligations questions, preserve canonical criteria; a test specification can supplement them or be a justified alternative only after evidence establishes sufficiency. Avoid hardcoding the example's wording or ID.
2. Give unresolved reasons a typed code plus separate explanation, or explicitly require the standalone code and place prose in rationale. The current free-text list invites a semantically clear response that machine consumers cannot recognize reliably.
3. Keep these failures as regression cases and add independently authored holdout questions that distinguish required behavior, test specifications, declared links and execution proof before integrating a fallback policy. Do not optimize minimality at the expense of required source content.

This review accepts the evidence and the isolated lifecycle implementation, not all semantic behavior. The original score, new failures and approval/AC statuses remain unchanged. No classifier is trained, promoted or automatically bypassed, and no search method, query or final retrieval answer has been validated here.
