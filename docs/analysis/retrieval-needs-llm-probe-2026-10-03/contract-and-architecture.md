---
title: LLM retrieval-needs interpretation experiment contract
description: Existing classifier and approval facilities, minimal host-operation seam and independently reviewed evaluation agreement.
type: explanation
status: draft
created: '2026-10-03'
last_updated: '2026-10-03'
components: [knowledge_management, decision_kernel]
---
# Retrieval-needs interpretation through the existing host workflow

This note was prepared before new LLM outputs. Source inspected at `2d4bee9fe665bc2f9b173baa752081bde69bc34c` on `experiment/retrieval-needs-single-call`. The user asked whether a suitable classifier already exists and proposed building the LLM path next. This is a standalone interpretation experiment; it does not integrate retrieval, activate a classifier, approve policy or establish end-to-end answer quality. The prior Jev probe, twelve-case gold and saved receipts remain immutable baseline evidence.

## What exists today

| Existing source | Actual responsibility and limit |
|---|---|
| [Intake classifier](../../../kernel/intent/classify.py) | Versioned Jev choice for decision/evidence/ideas/change/out-of-domain. It does not decide the search method. |
| [Research need planning](../../../kernel/capabilities/research/planning.py) | Jev selects six generic evidence categories; deterministic code maps these to configured sources. This is not a keyword/vector/traversal portfolio classifier. |
| [Retrieval mode helper](../../../integrations/retrieval_decision.py) | Deterministic keyword heuristics choose exact/test-link/component operations; Jev only resolves ambiguous skip/semantic/hybrid choices. It cannot serve as the requested complete method classifier. |
| [Registered query selection](../../../integrations/query_growth.py) | Jev selects among graph-capable query descriptors and build/clarify/skip; execution currently uses graph mode. This is query catalog selection, not the whole portfolio. |
| [Capability contracts](../../../kernel/contracts/capability.py) and [registry loader](../../../kernel/registry/adapter.py) | Typed descriptors carry versions and admission references; snapshots carry hashes. Admission is a declared record, not a classifier-quality evaluation and promotion service. |
| [Decision approval](../../../kernel/capabilities/decision/approvals.py) | Real persisted human approval/editing of proposed options and criteria, final recommendation and preferences. No general classifier training/repair/approval/activation pipeline is implemented by this module. |
| [Host fallback](../../../kernel/registry/fallback.py) | An eligible bound host operation can satisfy an unsupported output contract within permissions/scope/budget. A denied native action cannot acquire permission through fallback. |
| [Host operation registry](../../../kernel/capabilities/host/registry.py) | Existing operations are generate_options, synthesize, research, formulate_question and query_build. None returns a typed retrieval-needs interpretation. |

[ADR-053](../../architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md) distinguishes bounded Jev judgment from generative interpretation. LLM-created reusable options/criteria remain proposals until their applicable approval rule accepts them. That policy does not mean every ordinary interpretation of an already authorized question requires a fresh human approval. A future classifier artifact lifecycle still needs an explicit contract and proof; this experiment does not invent that pipeline.

## Smallest compatible implementation

Add one typed `host.retrieval_needs` operation, request/output schema lookup and deterministic host compiler/conversion. Expose it only through an experimental registry snapshot and environment overrides, without activating a default descriptor or replacing existing research routing.

Run the real existing `KernelService` path: start the isolated task, persist its operational input artifact and host packet, let the external host interpret the packet, validate the submission against the current wait, resume, and return the typed proposal. Reuse the kernel's LangGraph scheduler, interaction ledger, actor/revision checks and output conversion. Do not add a second pause protocol or direct model client inside the kernel.

The existing host operation is a handoff, not a configured generic text-generation API. The calling host performs model work; available model/token information must be reported honestly. A generic packet, an unregistered output schema or a findings string in host.synthesize is not a substitute for this typed seam.

## Input and output contract

The new request preserves the frozen original question, bounded supplied context, known ID candidates, trusted source-scope envelope and the same five catalog mappings: entity types, target IDs, required fields, document types and relationships. Literal target candidates may be extracted deterministically before fingerprinting. No previous Jev output or expected answer is given to the baseline host worker.

The output contains the original question/scope, selected and uncertain labels in all five dimensions, the existing detail/completeness/hierarchy/scope-resolution choices, unresolved reasons, concise rationale and `decided` or `needs_resolution`. It identifies the host-LLM route, while actual known model identity comes from submitted usage; absent usage stays unknown. No fabricated probabilities imitate Jev's output. The route label does not turn a scripted test fixture into evidence of a real LLM run.

System validation enforces question/scope identity, offered labels, grounded targets, essential missing dimensions and resulting status. Unknown meaning is preserved explicitly. Required fields mean indispensable answer facts, not every potentially useful supporting field. One AC's test requirements must not force a population choice; broad discovery must not require a fabricated ID; literal user targets outrank conflicting context. Context cannot grant authority. A known unsupported topic remains unresolved with its original question intact.

This version has no method-choice output, query arguments, endpoint selection, keyword generation, retrieval execution or policy approval. Those are separate consumers or later capabilities. It deliberately measures whether an LLM can supply the needs packet better before integrating that packet.

## Existing AC mapping and gap

| Existing approved AC | Current work status | Partial experiment coverage |
|---|---|---|
| KM-500e-1 | in_progress | Interpret requested facts/scope and preserve the original need through the host wait/resume. Query selection and final sufficiency remain outside this run. |
| KM-500e-2 | in_progress | Preserve distinct field meanings and explicit missing needs. Actual canonical fields, locators and disclosure remain outside this run. |
| KM-500a-1 | done | Reuse missing-input/failure distinctions and existing interaction handling. This does not re-prove the full research clarification behavior. |
| KM-500a-2 | done | Future consumer must select only eligible registered operations; this experiment does not select or run them. |
| KM-500c-2 | done | Preserved obligations are future inputs to actual evidence assessment, not proof that a question is answered. |

No statuses, approval records or AC IDs change. No inspected existing AC establishes a generic classifier artifact version/evaluation/approval/activation lifecycle; that remains an explicit gap. A separate planning project for that lifecycle is not part of this user-authorized experiment.

## Evaluation agreement frozen before output

Use the existing twelve question/context/catalog inputs and baseline semantic predicates unchanged. Keep original gold and Jev results untouched. A separately versioned comparison adapter translates only engine-specific observations: the payroll case's explicit unsupported marker and unresolved status replace a Jev-only probability requirement; one accepted host operation and zero Jev calls are transport facts, not proof of one underlying generative-model request.

Preserve the original seven-of-twelve Jev result. Report any prospective minimality/consistency overlay separately, applying its predeclared checks equally to saved Jev and new LLM output. In particular, exact-criterion questions need no indispensable test-link field, status-only questions need no indispensable criteria/test-spec fields, a code-flow subject need not be a known canonical entity, and selected schema needs must not silently lose the necessary schema document source.

Deterministic tests should exercise actual persisted input artifact -> packet -> submission -> same-flow resume, including wrong wait/revision/actor, malformed and extra fields, unoffered IDs, altered question/scope, unsupported/uncertain output and unknown usage. Positive and negative controls must use the same validator. Inspect the real operational artifact references, including telemetry excerpt-policy cases, so a valid-looking packet cannot hide omitted input.

Any actual LLM worker must consume only its designated packet and referenced input, without expected labels or prior outputs. Its result remains host-reported interpretation, not source truth. No external provider call is authorized by this document; the previously approved twelve TypeSafe cases remain a separate completed evaluation.