---
title: Optional model-neutral retrieval input preparation
description: Issue S2 analysis of query arguments, five search suggestions and existing kernel host boundaries.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-02'
components: [knowledge_management, decision_kernel]
---
# S2: optional preparation, not a second execution engine

Recommendation: introduce two narrow registered host operations for query-argument proposals and five search suggestions, using the existing kernel child/wait/submission lifecycle. Keep Jev's choices bounded: bind, discover, clarify or generate; then accept, correct, discover, clarify or stop. Jev never authors arguments, terms, canonical IDs or database syntax. Known caller inputs and methods requiring no terms bypass generation. The generation contract requires exactly five useful, distinct suggestions; it does not require five network calls, five searches or one suggestion per attempt.

This is analysis only, against `887c66d3896ba7727ce41b743887210a3883c6ce`. No implementation, AC/status edit, paid call or hosted write was performed. The research-agent, test-writer and IT-PO templates were read as research/test/interface guidance; their ticket, AC mutation and signoff workflows were not invoked. The explicit report request governs this artifact.

## Evidence and current limits

The old completion-gap report correctly labels S2 missing. The registered-query and search-preparation target flows remain `spec`/`draft`, all relevant steps `not_started`, with empty `implements`. They are requirements, not runtime evidence. RS-06, RS-07 and RS-08 were not run in the latest retest. The graph-only lane's two live starts reached research, returned zero answers and stopped at duplicated technical population clarification; the separate default-source lane reached a synthesis handoff, as recorded in the consolidated index. That is an upstream fact, not proof that optional generation is the immediate blocker.

| Verified current seam | What can be reused; what is absent |
|---|---|
| `kernel/capabilities/host/registry.py::OPERATIONS` | Exactly five implementations: `GenerateOptions`, `Synthesize`, `Research`, `FormulateQuestion`, `QueryBuild`. No argument or term preparation operation. `compiler_for` has a generic template, but `host_operation` returns `None` for unknown IDs. |
| `kernel/capabilities/host/executor.py::HostOperationExecutor`; `kernel/bootstrap.py::build_bindings` | Host descriptors receive a versioned binding. `ainvoke` raises `HostBindingExecuted`: the kernel never calls a generative model through this executor. |
| `kernel/adapters/{codex,claude_code}/SKILL.md` | The external host receives `waiting_host`, performs only the packet operation, writes schema-valid JSON, and resumes. This is the actual generative execution boundary. There is no demonstrated generic provider dispatch behind a packet. |
| `kernel/providers/base.py::JevPort`, `QuestionSpec`; `kernel/config.py::JevConfig`, `HostConfig` | The provider port exposes bounded `noul`/`choice`/`score` assessments. `jev.model` configures Jev. `HostConfig` has enablement, fallback, repair and input-size settings, but no generative model/provider selector. Do not relabel `jev.model` as the preparation model setting. |
| `kernel/capabilities/host/base.py::HostOperation`; `compiler.py::render`; `spec.py::COMMON_REQUIREMENTS` | Reuse request/output models, deterministic redacted compiler, schema attachment, prompt fingerprint and restriction to one operation. A malformed request currently falls back to generic wording; new preparation must be validated before dispatch, not accept this fallback as successful preparation. |
| `kernel/interaction/results.py::result_from_submission` | Known operations perform dedicated conversion; unknown host capabilities may use schema-validated pass-through. Neither generic compilation nor pass-through supplies preparation semantics, query binding, a usable provider, or proof of execution. |
| `kernel/interaction/packets.py::build_host_request`, `write_input_artifact`; `kernel/scheduler/nodes_interaction.py::open_interactions`, `await_interaction` | Persist redacted artifact/packet, wait with LangGraph interrupt, revalidate on resume. Host work is served sequentially. Reuse this; no new queue, checkpoint store or polling loop. |
| `kernel/interaction/submissions.py::check_submission`; `kernel/interaction/ledger.py::submit_interaction` | Already checks run/interaction/revision/actor kind/schema and references; first-write-wins ledger makes identical accepted replay idempotent and conflicting replay `not_pending` with `conflicting_duplicate`. Existing semantic context does not compare a retrieval query/version/source binding; S2 must add that exact check. Actor-kind checking is not proof of a particular provider/model identity. |
| `integrations/query_graph.py::build_query_growth_graph`; `query_growth.py::_arguments`, `_resume`, `_continued` | Graph has select/execute, clarification and build/admission waits, but no preparation phase. `_resume` recognizes only clarify/building/admitting. `_arguments` currently derives `entity_ids` from component IDs and treats every string-list argument as component scope; do not reuse that as universal argument validation. Exact-mode/catalog repair belongs to the adjacent issue. |
| `knowledge/query_catalog.py::builtin_descriptors`; `knowledge/query_models.py::QueryDescriptor`, `validate_arguments` | Reuse operation/version/digest, purpose, supported questions, typed parameters and result meaning. Dynamic recipes accept bounded strings/string lists and reject unknown inputs; built-ins need their own neutral request validator. Result meaning is not yet a complete per-query output-field/coverage contract. |
| `kernel/capabilities/retrieval/terms.py::build_query_terms`; `retrieval/executor.py::RepositoryRetrievalExecutor.ainvoke` | Existing extraction is deterministic: tokenize/deduplicate hints, question and technologies within `max_query_terms`. It is neither five-suggestion generation nor a preserved per-contract caller-term bypass. Feeding generated phrases back through it can split/change the accepted suggestions; the search owner must define the consumer mapping explicitly. |

Relevant source references: [host registry](../../../kernel/capabilities/host/registry.py), [query graph](../../../integrations/query_graph.py), [term extraction](../../../kernel/capabilities/retrieval/terms.py), [latest retest](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/results.md), [old gap analysis](../2026-10-02-retrieval-completion-gap-analysis.md), [query target](../../product-truth/flows/leafcutter/retrieval-registered-query.flow.json), [search target](../../product-truth/flows/leafcutter/retrieval-search-preparation.flow.json).

## Viable options

| Option | Benefit | Cost / boundary |
|---|---|---|
| Two typed operations, proposed `host.prepare_query_arguments` and `host.generate_search_terms` | Small explicit contracts; independently testable converters and permission/cost declarations; cannot mistake terms for arguments. Closest to `QueryBuild`'s candidate-only result. Recommended. | Two registry/schema/template entries and parent continuation branches. Factor shared binding/validation, not the distinct output meanings. |
| One registered `host.prepare_retrieval_inputs` with a strict discriminated union | Shared lifecycle and configuration; lower registration count. | Must prove kind-specific schemas and impossible cross-kind outputs; one operation can conceal unrelated correction paths. Viable if the union remains closed and each branch has its own validator. |
| The same typed operations served by an explicit configurable external provider adapter | Enables unattended execution and measured model/token receipts while preserving the kernel protocol. | Adds real provider dispatch, timeout/retry and credential/data-policy work. No such generative adapter was found in the inspected host/provider path. Stage after the existing cooperative-host route, not a prerequisite or a claimed existing feature. |

Reusing `host.synthesize`/`findings.v1` as a JSON container is not a viable shortcut: its converter turns claims into attributed inferences, not validated query arguments. `host.generate_options` has proposed decision-option semantics; `host.query_build` authors new recipes for admission. None should silently acquire argument/term semantics.

## Smallest staged reuse and node ownership

First preserve a selected, pinned contract and validated known-input bypass. Then add the two typed host operations and a real host client execution/resume proof. Finally add bounded semantic corrections and, if needed, an unattended provider adapter. Local contract tests can precede any authorized live model test. Do not claim the complete search portfolio or answer-assessment loop as delivered by this slice.

Every proposed node has exactly one runtime owner:

| Node | Owner | Input -> output / routing |
|---|---|---|
| `collect_preparation_context` | System | Selected contract plus trusted caller/context values -> per-contract known values with origins; no invented facts. |
| `choose_preparation` | Jev | Offered feasible choices -> bind/discover/clarify/generate only; no free-text value fields. Known-term/no-term bypass is explicit. |
| `bind_known_inputs` | System | Authoritative values -> candidate arguments/terms using the selected contract. No forced five-term padding on bypass. |
| `request_discovery` | System | Bounded missing-fact request -> existing retrieval child and persisted continuation. A full search transfers ownership to the search/attempt flow; terms-only help does not execute a full search child. |
| `request_clarification` | System | Missing intent/authority identified by the decision -> existing human wait; the human supplies the answer, never a host impersonation. |
| `request_generation` | System | Pinned contract/context and policy -> ordinary registered host child/wait; checks availability, permissions and budget first. |
| `generate_arguments` OR `generate_terms` | Host LLM | Typed packet -> proposal or explicit unresolved/failed result. Generation belongs to the host operation boundary, not an inline Jev call. |
| `validate_preparation` | System | Known or resumed proposals -> binding/schema/scope/provenance-valid inputs, or rejection. No query/search yet. |
| `judge_preparation` | Jev | Valid generated proposal + original question/output obligations -> accept/correct/discover/clarify/stop. Structural validity does not establish usefulness. Known-term bypass skips generation-only judgment. |
| `handoff_accepted_inputs` | System | Accepted inputs + pins -> exactly one selected-query/search handoff, with preparation provenance; execution and shared assessment remain their existing/adjacent owners. |

Use `query_planning.waiting`, normal `RequestProposal` children and `current_wait` outcomes. Extend the parent phase enum/expected-schema mapping deliberately; accepted preparation must not fall into `_continued`'s activation-receipt branch. A semantic correction is a new bounded child with new wait identity and retained prior attempt; it cannot reset the original run budget or replay selection. No unchanged retry to seek a higher confidence score (ADR-053).

## Contract and model configuration boundary

New names below are proposals, not existing schema IDs. Register request/result models through `schema_ids.KNOWN_SCHEMA_IDS`, `schema_catalog.SCHEMA_CATALOG`, committed JSON Schemas, capability registry and the fixed host-operation table together.

- Shared request binding: preparation ID, original question/need ID, selected method/operation, operation version and digest, selected input contract and output obligations, repository ID, source/revision/generation identity where applicable, approved filters/scope, known values with caller/evidence origins, and remaining preparation allowance. Keep these pins in the kernel continuation; echoed host fields never become authority. Include a deterministic contract/request digest so descriptor content changes under the same version cannot silently validate.
- Argument proposal result: matching binding plus `arguments`, per-argument basis references, and `unresolved_inputs`. Only declared fields/types may appear. Immutable repository/generation/permission values are system inputs, never authorable arguments. Canonical IDs must be literal trusted caller values or source-backed discovered values of the required kind. An unresolved required fact or two plausible contract IDs routes to discovery/clarification; syntactic validity and Jev confidence cannot manufacture the missing fact.
- Term proposal result: matching binding plus either `status=proposed` and exactly five bounded nonblank suggestions, or an explicit inability/unresolved outcome that cannot search. Deterministic uniqueness uses documented normalization (at least trim, whitespace collapse and casefold); five spelling variants cannot pass. Jev checks semantic diversity and usefulness against the original question. Suggestions remain inputs, never evidence/facts. Do not pad a four-term result or silently trim six to five.
- Both outputs prohibit extra fields such as approval, scope expansion, executable query text, model-selected follow-up operations or changed limits. Cross-check the authoritative selected contract again immediately before execution. A valid result for query A is not permission to execute query B, another version, another source, or another method. Explicit compatible reuse needs revalidation and a recorded binding.
- Configure provider/model/settings through trusted host execution configuration/profile, separate from the semantic payload and `jev.model`. Pin the requested profile/config fingerprint with the wait; report resolved provider/model/settings and known usage in a receipt. This profile boundary is new work: current host adapters use the active host session and cannot promise arbitrary in-session model switching. Unsupported configured models produce explicit unavailable results; they do not silently fall back. No hardcoded Haiku, vendor name or model identifier in product schemas or Jev choices. Two model configurations must accept the same public input/output contract.

## Budget and permission clauses that need explicit work

`kernel/registry/eligibility.py::_policy_code` checks declared permissions, allowed effects and host-operation capacity before selection; `nodes_route._bind_descriptor` increments that counter. `guards.account_usage` records known/estimated costs and unknown calls. `HostOperation` conversion preserves reported usage; `host_usage` leaves unknown model/tokens/cost unavailable. Preserve these mechanisms and the Jev reserve-before-use boundary.

Do not overclaim their strength. `HostConfig.enabled` currently gates research planning/fallback, not every host descriptor in generic eligibility; S2 must explicitly gate optional preparation. A finite host-operation count is not a hard token/dollar cap on an external model. Repairs in `await_interaction` are bounded by `max_repair_attempts` inside one interaction, and rejected submissions do not go through accepted-result usage accounting. Thus opaque provider retries or repeated generative repairs would hide calls/costs. Initial adapter execution should have no hidden retries; each semantic regeneration must be a newly budgeted child. Define and test how any schema-repair model call is reserved/reported once, including failed calls, before promising a strict per-call cap. If reporting is unavailable, show unknown cost and the actual operation/repair caps; never report zero-cost generation.

Host preparation must not read new files or call search independently to invent a basis. Discovery uses authorized existing retrieval. Denied scope/provider permission cannot trigger a fallback to another model, source or query. Redact approved context before packet/artifact persistence and transmission, and preserve limits when resuming.

## Exact AC mapping and missing clauses

All listed records currently have `status=active`, `req_status=active`, `readiness=approved`; these are recorded statuses, not a new acceptance judgment. No AC is edited here.

| Existing ID | `work_status` | Existing coverage / missing S2 clause |
|---|---|---|
| `KM-500a-1` | `done` | Missing-input clarification and same-need resume. Extend with bounded bind/discover/clarify/generate choice, authoritative argument bases, unresolved generation and no host-authored facts. |
| `KM-500a-2` | `done` | Registered catalog selection and validated bound arguments. Extend with selected query/version/digest/input AND output contract binding across preparation, wrong-contract rejection and duplicate-proof execution. |
| `KM-400e-2` | `done` | Deterministic obvious requests and bounded method choice. Preserve no-extra-model behavior; add explicit caller-term/no-term generation bypass and provenance. Existing exact-mode proof does not establish RS-07. |
| `KM-500e-1` | `in_progress` | Preserve original question, resolved scope and required fields. Extend preservation through a preparation wait; unrelated count population must not become a requirement for exact/term inputs. The observed live scope defect is owned upstream. |
| `KM-500c-2` | `done` | Evaluate actual evidence and original needs. Preserve boundary: preparation success is neither query success nor answer success; accepted terms/proposals never count as retrieved evidence. Assessment implementation belongs to its analyst. |
| `KM-500g-2` | `in_progress` | Matching-attempt/revision diagnosis and honest unknowns. Preserve separate unavailable, invalid, rejected, exhausted and unresolved preparation outcomes with known expected/observed pins. |

New behavioral clauses are required; no existing AC explicitly mandates an optional interchangeable-model host action, exactly five distinct nonempty useful suggestions, per-contract generation bypass, host model-config receipt, preparation-specific stale/version validation, or correction-call accounting. These need official AC IDs in later authorized authoring, not invented completion IDs here. RS-06/07/08 are scenario IDs, not substitutes for store ACs. `KM-500d-4` (`todo`) concerns chunked embedding readiness and is not a dependency of preparing keyword suggestions.

## RED and discrimination proof for later implementation

These tests are proposed and were not run. Follow the test-writer's reachability/seam/real-artifact/boundary/failure/discrimination rules; test failures must be behavioral, not import errors or symbol greps. Existing reference suites include `tests/kernel/interaction/test_submissions.py`, `test_host_repair.py`, `test_host_security.py`, `tests/kernel/capabilities/test_host_operations.py`, and `tests/knowledge/test_query_growth_adversarial.py`. They prove reusable facets, not the new preparation journey.

| Required executable proof | Plausible wrong implementation it must catch |
|---|---|
| Public `KernelService` selected-query path with real registry/serializer/compiler -> host wait -> result -> consumer. Observe proposed inputs actually used by the selected query; test registered host binding refuses native invocation. | Generic packet-only implementation; dead converter; output merely passed to a helper; generation inserted after query execution. |
| RS-07 with accepted caller terms and no-term method: zero generation packets/model calls, same terms/origins/pins delivered exactly once. | Unconditional generation; padding caller terms to five; loss through deterministic retokenization; use by all selected methods. |
| RS-08 success with five distinct suggestions; 0/1/4/6, whitespace-only, case/spacing duplicates, oversize or wrong-type terms; five syntactically distinct but irrelevant suggestions rejected by bounded usefulness decision. | Nonempty-list validator; deduplicate-and-pad; Jev acceptance overriding schema; usefulness inferred from shape. |
| RS-06 canonical ID omitted, discovery yields two IDs: clarification; invented ID, wrong entity kind, foreign basis reference and valid-but-unsupported argument produce zero backend calls. | Component ID reused as entity ID; free-text Jev arguments; LLM plausible ID accepted as fact. |
| Query A v1/digest/source wait resumed with A v2, changed digest, query B, another need or foreign generation: reject and retain original question/obligations. Test same version with changed contract. | Check schema only; trust echoed query fields; bind generated input globally. |
| Stale revision, foreign run/interaction, wrong schema, host-as-human, cancellation; identical accepted replay and conflicting duplicate; fresh-process restart before/after acceptance. Assert one execution and stable saved budget/provenance. | Duplicate execution; fresh wait resetting budget; idempotent conversion masking repeated backend call. |
| Host disabled, descriptor unavailable, denied permission or zero remaining host budget: no generation; remaining budget one permits one operation, next correction stops. Exhaust Jev budget before usefulness judgment: no execution. | Assuming `host.enabled` is a universal gate; fallback on denial; fresh child reset; execute on absent judgment. |
| Invalid output then bounded correction; provider timeout/failure and schema repair preserve used calls, unknown costs and prior inputs. No opaque retries; accepted replay adds no usage. | Only successful calls counted; schema repair unlimited under one host-operation reservation; unknown cost replaced by zero. |
| Two host model profiles return the same typed contract, with distinct accurate receipts; unsupported model fails explicitly. Context contains instruction-like text or secret: data stays data and redaction survives artifact round-trip. | Haiku-hardcoded branch; profile supplied by untrusted output; forged model identity treated as verified; prompt text changes scope. |
| Multi-contract preparation: known terms for A, generation for B; five suggestions do not imply five calls. Terms-only support returns to argument preparation, while full search produces its own attributable attempt. | Global term bag; unconditional fanout; term-generation child secretly executes search; double entry to shared comparison. |

## Dependencies and handoff

Upstream: repair the observed answer-scope gate and the selected-query catalog/argument-binding issue; expose each selected contract's required inputs, output obligations, source pins and a minimal stable attempt/preparation identity. S2 can be built/tested as a narrow registered child before the entire method portfolio is complete. It must consume that portfolio's identity contract rather than invent a parallel attempt history.

Search owner: consume validated per-contract terms with an explicit phrase/token mapping; choose combined-term search versus separately attributable query variants under actual method/call budgets. Five preparation suggestions alone decide neither fanout nor vector readiness. Query owner: enforce its real neutral input validator and mode. Assessment owner: judge returned evidence, never generation output. Host integration owner: explicit model profile, true availability, usage receipts and any provider adapter. No traversal, advisory memory or generic plugin framework is required to implement this slice.