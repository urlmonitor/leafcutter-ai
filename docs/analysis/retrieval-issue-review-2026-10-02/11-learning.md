---
title: 'Issue 11: Advisory retrieval learning and later reuse'
description: 'Historical analysis and saved observations for Issue 11: Advisory retrieval
  learning and later reuse.'
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# Issue 11: Advisory retrieval learning and later reuse

Analysis only, 2026-10-02. Verified HEAD: `887c66d3896ba7727ce41b743887210a3883c6ce`. Scope: S7 / RS-04, RS-16, RS-28. No runtime, AC/status, database, provider, publication or PR changes; no tests executed.

**Recommendation:** add a distinct advisory-observation family to the existing `kernel.memory` owner. Jev evaluates actual retrievals against the original question; System preserves that bounded observation and automatically admits valid advice for later planning. Keep human-approved DecisionRecords unchanged. Automatic advisory publication needs its own explicit authority contract, not a human approval step for every observation.

## Evidence boundary

Read root/deployed CLAUDE guidance and research-agent, test-writer, BA and IT-PO prompts. Applied their factual research, observable boundary, producer/consumer and discriminating-test principles; this is the expressly requested analysis, not AC authoring or workflow execution. See `.claude/agents/test-writer.md` under “Test Angles” and “Real-Artifact Behavioral Test Mandate”; BA lines 52-75/413-435; IT-PO lines 587-605.

The [old gap analysis](../2026-10-02-retrieval-completion-gap-analysis.md) identifies S7 as missing. The [target journey](../../product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json) is draft/spec: `compare -> remember -> combine`, followed by final assessment. Its `offer-methods` and `plan` require compatibility and Jev applicability. These are proposed behavior.

[New method-attempt analysis](05-method-attempts.md) supplies the missing durable attempt contract; [comparison analysis](09-compare-combine.md) supplies observed judgments before combination. Neither implements memory. The [fresh retest](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/default-source/results.md) totals 18 Jev calls, four starts and zero final answers. RS-04/16/28 full journeys were not run. Native synthesis handoffs and graph-only clarification stops prove neither strategy persistence nor later reuse.

## Existing owner, transport and limits

| Verified source anchor | Reusable mechanism; boundary |
|---|---|
| `kernel/capabilities/base.py:85`, `kernel/bootstrap.py:261` | ExecutionContext already receives configured `ColonyMemory`; extend this seam instead of constructing a separate store inside research. |
| `kernel/memory/models.py:129,184`; `builder.py:138` | Approval permits only approved human actors; records require a selected option. Builder refuses unresolved/unapproved decisions. A tie, no winner or machine observation cannot honestly be disguised as a DecisionRecord. |
| `kernel/memory/port.py:66` | Bounded find/get/stage protocol and null backend; today all methods are decision-specific. Add typed advisory methods/results without weakening existing methods. |
| `kernel/memory/staging.py:52`; `file_store.py:69,144` | Stages only into the owning run's artifacts; write failure returns no record. Useful isolation and failure semantics, but staging alone does not make a later run find advice. |
| `kernel/memory/codec.py:63,84,113`; `file_store.py:102,116` | UTF-8 serializer, bounded reads, atomic writes and indexed hash validation are reusable techniques. Existing parser/index schema explicitly handles DecisionRecords; generalization is real work. |
| `kernel/memory/publish.py:149,217` | Explicit decision publication validates before writing and rebuilds the index. Individual writes are atomic; the whole batch is not one transaction. Do not treat an orphaned record or failed index update as admitted advice. |
| `kernel/memory/precedent.py:91,131,151,270,282` | Candidate filtering, Jev applicability and human-confirmed reuse exist for approved decisions. Reuse the pattern, not its decision-resolution or approval behavior. |
| `kernel/capabilities/research/state.py:38`; `executor.py:265` | Persisted continuation exists; current graph is plan/collect/evaluate/finish with no advisory lookup/write loop. |

`tests/kernel/memory/test_learning_loop_e2e.py` demonstrates the scope of existing tests: scripted Jev, real stores, explicit publication and human-confirmed decision reuse. This is not evidence for automatic retrieval advice or improved real-model quality.

## Options

| Option | Tradeoff |
|---|---|
| Encode advice as approved decisions or invented selected options | Superficially small; corrupts authority and cannot represent null winners. Reject. |
| New advisory family under `kernel.memory` with typed transport, admission and index | Preserves ownership and backend substitution; requires distinct lifecycle/schema and research nodes. Recommended. |
| Mine telemetry or create another strategy database | Faster experimental capture, but duplicates durable identity, retention, permissions and lookup ownership. Trace existence also says nothing about usefulness. Reject as production design. |

## Minimal advisory contract

Proposed `RetrievalStrategyObservation` has `kind=retrieval_strategy_observation`, version, immutable observation ID/content hash and `authority=advisory`. It has no human approval field and never projects as canonical historical truth. Record bounded fields or immutable artifact references, respecting the existing read/disclosure policy:

- **Question/context:** root request/run/work-item IDs; exact original question or authorized retained reference/hash; immutable answer-obligation version; clarified scope and constraints. Retain child need separately; never replace the original question with its prefixed subquestion.
- **Attempt identity:** actual attempt/receipt IDs, ordered method combination, method contract/version, query ID/version/digest/admission receipt, accepted arguments, terms/filters and their caller/deterministic/host origin; traversal frontier/visited artifact references where applicable.
- **Execution conditions:** repository/workspace identity, requested and actual source SHA, generation, mapper and source-role identities; policy/kernel/schema versions; preparation/evaluation model identifiers/settings and prompt/template versions; allowed and consumed budgets, latency/cost and unknown measurements explicitly null.
- **Observed result:** execution status separate from usefulness; evidence/result hashes and locators, coverage/field availability, limits, failures and actual comparison snapshot. Jev provenance identifies assessed inputs and judgment version; remote trace verification is separate from a trace ID.
- **Outcome linkage:** initially `final_fulfillment=pending`. Later immutable event names this observation, answer/assessment ID/hash/version and actual fulfilled/partial/blocked/failed/unknown state. Assessment completion and caller delivery remain separate; returned/acknowledged needs its actual receipt. Corrected assessments append superseding events; they never rewrite the original judgment.

Comparison carries outcome `preferred | tie | complementary | no_useful | incomparable | unassessed`, nullable preferred attempt, retained contribution IDs and bounded reason codes. One actual attempt records usefulness with no comparative winner. Waiting, empty-success, denied, failed and unexecuted attempts stay distinct. Budget-confounded preferences are conditional observations, never causal superiority. No free-form Jev prose or estimated missing fields are fabricated.

## Phased graph and publication

**Phase A: capture and failure isolation.** Extend the existing research LangGraph after S5 validation. `stage_advice` (System) writes once before combine or changed-plan routing and checkpoints its receipt/error. `combine` (System/S5) proceeds regardless of memory availability. Final answer assessment remains owned by sibling 04; after the answer is finalized independently, `append_answer_outcome` (System) attaches only the actual terminal assessment. An interrupted/waiting answer stays pending. Stage-only delivery is explicitly **incomplete learning**.

**Phase B: automatic closed loop.** Add `admit_advice` (System, memory owner): validate schema, producer receipts, references, policy/scope and idempotency; publish automatically into a bounded advisory namespace/index under the same configured memory backend. No per-record human signoff. This is a new authorized advisory-write contract, not an invocation of decision publication or permission to write canonical Git history. The runtime retains run-local staging; the memory publication owner controls shared durable admission. Publish a discoverability receipt only after index/record consistency succeeds. The configured durable root must survive the originating process/worktree; define retention, deletion and repository isolation in this same owner.

On a later process, `find_advice` (System) returns bounded admitted candidates. `check_compatibility` (System) rejects or flags stale/incompatible source, field meaning, query/schema, model/prompt, scope and access conditions. Default to exclusion where compatibility is unknown; explicit versioned policy may admit a justified cross-version comparison, never silently. `judge_applicability` (Jev) assesses compatible advice for the current original question; `offer_methods` (System) still offers only currently authorized capabilities; `select_methods` (Jev) chooses from that offer. Stored preference cannot select a method automatically. Fresh execution and proof remain required.

**Phase C: evaluate usefulness.** Independently reviewed cases compare advice-on/off under declared conditions. This measures governed strategy reuse; it is not model-weight training. Preserve held-out cases and exclude leaked evaluation/oracle documents from independent quality claims.

All nodes have one runtime owner. Kernel continuation, budgets and scheduler remain authoritative. Snapshot-derived idempotency keys distinguish new comparisons from replay; retries repair only memory delivery. Failed staging/admission/outcome append produces a typed visible limitation, preserves answer/evidence, and never restarts retrieval or spends another judgment call. Unavailable memory falls back to ordinary planning.

## AC disposition and dependencies

All following ACs are active/approved; work status is not proof of this target:

| Exact AC | Work status | Treatment |
|---|---|---|
| KM-400c-1 | done | Preserve reviewed canonical-history boundary; advisory records remain distinct. |
| KM-500c-2 / KM-500c-3 | done | Reuse original-question assessment and bounded no-progress behavior; add advisory receipt/resume contract. |
| KM-500d-3 | in_progress | Complete independent evaluation/invalidation; limits learning claims, does not implement memory. |
| KM-500f-2 | in_progress | Keep declarations, execution and deployment proof separate. |
| KM-500g-1 / KM-500g-2 | in_progress | Preserve matching-attempt observation/diagnosis; no trace or root-cause invention. |

New focused subordinate contracts are needed for advisory schema/capture, automatic admission, later applicability and outcome/failure handling. Allocate IDs through later BA/IT-PO work; no criteria/status edits here.

Inputs: S1 supplies immutable attempt receipts and consumed budgets; S5 supplies validated comparison snapshots; sibling 04 supplies original obligations and final assessments; S6 supplies bounded changed-plan routing; source/catalog owners supply compatibility identities. Outputs: S5/S6 receive record reference or typed limitation; future planning receives bounded compatible advisory candidates and applicability notes; evaluation receives attributed observations with separate publication/finalization states. Memory never owns retrieval, method selection or answer fulfillment.

## Required RED and negative proof

Use actual serializers, file backend, admission consumer and public research entry points with controlled Jev. Capture behavioral RED before coding; test syntax/import failure is not RED proof.

1. Compare real producer outputs, stage before combine, append only after actual final assessment. Tie/no-winner/one-attempt cases round-trip. Mutants: prefilled fulfilled status, fabricated winner, child question replacing original.
2. Fresh process automatically discovers admitted advice, Jev may reject it, and current selection executes fresh evidence. No human approval is forged or requested. A staged-only record must fail this closed-loop test.
3. Change source/query/mapper/field meaning/model policy; stale advice is excluded/flagged. Similar wording from another repository cannot cross scope. Unknown versions fail applicability admission, not the answer.
4. Malicious advice requesting an unoffered method, wider access, copied answer or executed-proof claim remains inert. Optimistic Jev cannot override deterministic checks.
5. Inject stage, index/admission and final-append write failures independently: answer and useful evidence survive; no retrieval repetition, duplicate observation, false publication receipt or budget reset.
6. Restart/replay at each write boundary; one immutable observation and one matching outcome survive. Reject foreign/stale outcome links; preserve pending when no terminal answer exists.
7. Null backend, missing artifact, tampered hash, oversized record, retained failure/no-useful advice and exhausted applicability budget degrade explicitly. Measure genuine later usefulness separately; scripted wiring tests and the 18-call retest cannot establish it.
