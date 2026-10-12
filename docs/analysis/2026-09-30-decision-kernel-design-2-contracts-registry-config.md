---
title: "Decision Kernel V0 Design - Part 2 of 6: Contracts, Registry and Config"
description: "Pydantic v2 contract definitions for every Revision 3 section 7 entity, the registered payload schema catalog, the new initially-empty capability registry file with its admission records, the registry adapter and eligibility filter API, the kernel configuration file with all keys and defaults, and secret loading."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

# Decision Kernel V0 Design — Part 2 of 6: Contracts, registry and config

Owner: **P1**, unless a row says otherwise. Spec: §7 in
[spec part 3](2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md) and §6 in
[spec part 2](2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md).
Back to [part 1](2026-09-30-decision-kernel-design.md).

## Model conventions (`contracts/base.py`)

- **`KernelModel(BaseModel)`** is the base for every contract.
  - Config: `ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)`.
  - Field `schema_version: Literal["1.0"] = "1.0"`.
  - Changes use `model_copy(update=…)`, so nothing mutates in place.
  - Collections use `Field(default_factory=…)`.
- **`PersistedModel(KernelModel)`** adds `id: str`, `created_at: datetime` and `updated_at: datetime`. A validator rejects naive datetimes (UTC only).
- **IDs.**
  - Assigned only by the kernel, never by a model.
  - Shape: `<prefix>-<16 hex>`, validated by the regex `^[a-z]+-[0-9a-f]{16}$`.
  - Prefixes: `run task req work inv ev find dec opt crit int gap evt ra`.
  - Content-addressed IDs:
    - `ev-` = `sha256(source.locator + "\n" + content_hash)[:16]`
    - `req-` dedup key = the fingerprint from part 3
  - All other IDs use `uuid4().hex[:16]`.
- **`created_seq: int`.** Kernel-assigned and monotonic. It gives a deterministic presentation order: sort by `(created_seq, id)`.
- **Serde allowlist.** `contracts/__init__.py` exports `ALL_MODELS: tuple[type, ...]`, covering every model and enum. The checkpointer allowlists exactly these (part 3).
- **Unknown fields are rejected** at every external boundary: TaskInput, InteractionSubmission and registry entries.

## Enums (`contracts/enums.py`, all `StrEnum`)

| Enum | Values |
|---|---|
| RequestKind | evidence, options, synthesis, human, capability |
| WorkItemStatus | ready, dispatched, waiting, completed, partial, blocked, failed, cancelled |
| ResultStatus | completed, waiting, partial, blocked, failed |
| RoutingOutcome | selected, insufficient_context, no_match, unavailable |
| DecisionStatus | resolved, needs_evidence, needs_options, needs_synthesis, needs_human, blocked |
| ApprovalStatus | not_required, proposed, approved, rejected |
| RunStatus | running, waiting_host, waiting_human, completed, partial, blocked, failed, cancelled |
| ExecutionMode | native, host_handoff |
| SideEffectClass | none, read_only, run_artifacts, repo_write, external_write |
| EvidenceCategory | authoritative_guidance, internal_principles, prior_decisions, existing_patterns, task_context, external_practices |
| MissingKnowledge | missing_task_fact, unknown_options, missing_decision_basis, missing_authoritative_guidance, missing_internal_principle, conflicting_evidence, missing_implementation_fact, human_preference_or_authorization |
| GapType | unsupported, host_only, provider_failure, permission, ambiguous |
| InteractionKind | host_work, human |
| FindingKind | source_fact, inference, assumption, human_input |
| Priority | required, supporting |

## Core contracts (field lists; spec §7.2–§7.9)

| Model (module) | Fields |
|---|---|
| `Actor` (task) | `id`, `kind`: human, host or service |
| `Scope` (task) | `workspace_id`; `repository_root` (absolute path, resolved and validated); `revision` (`commit`, `dirty: bool`, `tree_fingerprint`); `component_ids` (checked against `docs/components.json`); `read_roots` (relative, must stay inside the root); `source_ids`; `technologies` (task metadata for source resolution) |
| `Constraint` (task) | `id`, `kind`, `value: str \| dict`, `source_ref`, `severity` (must, should or may), `origin` (caller, policy, human or host), `approval_state` |
| `TaskInput` (task) | `goal` (1–4000 chars); `caller: Actor`; `scope`; `requested_output_schema` (default `leafcutter.decision_report.v1`); `input_payload_schema` and `input_payload` (optional; validated through the catalog); `initial_evidence: list[EvidenceInput]`; `constraints`; `permissions` (default `["read_repo"]`) |
| `Task` (task) | `id`, `root_task_id`, `parent_task_id`, `original_goal` (never rewritten), `intent`, `scope`, `evidence_refs`, `constraint_refs`, `requested_output_schema`, `root_work_item_id` |
| `EvidenceSource` (evidence) | `id`; `kind` (repository_file, knowledge_node, host_research, human, task_input); `locator` (`path#L10-L22`); `title`; `source_version` (commit plus dirty flag); `retrieved_at`; `observed_modified_at`; `section_locator` |
| `Evidence` (evidence) | `id`; `category`; `semantic_type` (repository_fact, documentation_fact, human_input, synthesized_finding, task_context); `excerpt` (≤ `retrieval.max_excerpt_chars`); `artifact_ref`; `source`; `content_hash`; `provenance` (producer, invocation_id, strategy, query, rank, relevance); `access` (internal or restricted); `verification` (unverified, host_reported or source_verified); `limitations`; `truncated` |
| `Finding` (evidence) | `id`, `claim`, `kind`, `supporting_evidence_ids`, `contradicting_evidence_ids`, `limitations`, `producer`, `producer_version` |
| `EvidenceNeed` (evidence) | `id`; `category`; `question`; `priority`; `acceptable_source_kinds`; `resolution` (source ids); `status` (open, satisfied, partial or unavailable) |
| `EvidenceBundle` (evidence) | `id`, `request_id`, `evidence_ids`, `finding_ids`, `coverage: dict[need_id, status]`, `attempted_sources`, `unavailable_sources: list[{source_id, reason}]`, `contradictions: list[{a, b, note}]`, `limitations`, `truncated` |
| `Request` (work) | `id`, `origin_work_item_id`, `kind`, `goal`, `question`, `payload_schema`, `payload: dict` (validated by the catalog in a model validator), `requested_output_schema`, `evidence_needs`, `priority`, `context_refs`, `depends_on`, `operation: str \| None` (registry operation the request needs; see eligibility), `dedup_key` |
| `RequestProposal` (work) | The same fields without `id` or `dedup_key`. Capabilities propose; the kernel assigns identity. |
| `WorkItem` (work) | `id`, `root_task_id`, `request_id`, `status`, `dependency_ids`, `child_ids`, `continuation: Continuation \| None`, `binding: Binding \| None` (`capability_id`, `version`, `execution_mode`), `attempts`, `depth`, `result_ref`, `routing_ref`, `interaction_ref`, `limitations`, `created_seq`, `updated_revision` |
| `Continuation` (work) | `capability_id`, `capability_version`, `state: dict` (validated by the capability's own continuation model), `resume_reason` (children_done, interaction_answered or retry) |
| `CapabilityInvocation` (work) | `id`, `work_item_id`, `capability_id`, `capability_version`, `input_payload_schema`, `input_payload`, `context_refs`, `continuation`, `child_outcomes: list[{work_item_id, request_kind, status, output_schema_id, result_ref, priority}]`, `input_fingerprint`, `attempt`, `trace: TraceContext` |
| `CapabilityDescriptor` (capability) | Registry entry fields (below) plus `registry_origin` (`registry_id`, `registry_version`, `entry_hash`) |
| `CapabilityResult` (capability) | `invocation_id`, `work_item_id`, `status`, `output_schema_id`, `output_payload`, `evidence`, `findings`, `decisions`, `requests: list[RequestProposal]`, `continuation_state`, `usage: list[Usage]`, `error: ErrorInfo \| None` (`code`, `message`, `retryable`), `diagnostics: dict[str, str \| int \| float \| bool]` |
| `Usage` (capability) | `provider` (jev, host or native); `model_id`; `input_tokens`; `output_tokens`; `duration_ms`; `cost_usd`; `cost_provenance` (reported, estimated or unavailable); `calls`. Unknown values stay `None`, never 0. |
| `Option`, `Criterion` (decision) | Option: `id`, `title`, `description`, `assumptions`, `source_refs`, `proposal_status`. Criterion: `id`, `question`, `priority`, `scope`, `decision_basis`, `weight_rule`, `approval_status`. |
| `CriterionAssessment` (decision) | `criterion_id`, `option_id`, `outcome` (pass, fail or uncertain), `evidence_ids`, `provider_answer` (raw probabilities and confidence), `limitations` |
| `Decision` (decision) | `id`, `question`, `option_ids`, `criterion_ids`, `selected_option_id`, `status: DecisionStatus`, `approval_status`, `evidence_ids`, `missing: list[MissingKnowledge]`, `rationale` (`text`, `origin` template or host), `versions`, `unresolved_risks` |
| `RoutingAssessment` (decision) | `id`, `work_item_id`, `eligible_candidate_ids`, `excluded: list[{capability_id, reason_code}]`, `selected`, `probabilities`, `provider_confidence`, `template_id`, `template_version`, `model_id`, `evidence_revision`, `outcome`, `reason_codes`, `thresholds`, `jev_called: bool` |
| `HostWorkRequest` (interaction) | `id`, `work_item_id`, `invocation_id`, `operation`, `goal`, `input_artifact_refs`, `input_evidence_ids`, `allowed_operations`, `forbidden_operations`, `output_schema_id`, `output_json_schema` (inline, from the catalog), `context_limits`, `trace_context`, `state_revision`, `attempt`, `rejections` |
| `HumanQuestion` (interaction) | `id`, `work_item_id`, `decision_id`, `question`, `relevant_evidence_ids`, `choices: list[{id, label, consequences}]`, `free_text_allowed`, `why_research_cannot_settle`, `required_actor_kind="human"`, `state_revision` |
| `InteractionSubmission` (interaction) | `run_id`, `interaction_id`, `expected_state_revision`, `actor: Actor`, `relayed_by` (e.g. `claude_code`), `response_schema_id`, `response: dict`, `new_evidence`, `usage` |
| `CapabilityGap` (run) | `id`, `gap_key`, `gap_type`, `goal`, `normalized_need`, `request_kind`, `input_schema`, `output_schema`, `scope_component_ids`, `registry_snapshot_hash`, `candidates_considered`, `why_insufficient`, `occurrence_count`, `example_run_ids` (≤5), `fallback_outcome` (none, host_completed, host_failed or blocked), `missing_native_capability`, `proposal` (author `template`), `first_seen`, `last_seen` |
| `RunEvent` (run) | `seq`, `run_id`, `kind` (e.g. `work_item.created`, `routing.assessed`, `guard.tripped`, `submission.rejected`), `at`, `refs: dict[str, str]`, `detail` |
| `RunEnvelope` (run) | `run_id`, `root_task_id`, `state_revision`, `status: RunStatus`, `output` (`schema_id`, `payload`), `report_ref`, `decision_ids`, `evidence_ids`, `open_questions`, `pending_interaction` (HostWorkRequest, HumanQuestion or None), `limitations`, `gaps`, `usage_summary`, `trace_refs` (`trace_id`, `trace_url`, `observability` ok or degraded), `errors` |

`CapabilityResult` model validators enforce the §7.6 lifecycle invariants:

- `completed`: no requests and no continuation.
- `waiting`: at least one request and a continuation.
- `partial`: at least one limitation in `diagnostics` or the output.
- `failed`: `error` is set.

## Payload schema catalog (`contracts/payloads.py`, `contracts/schema_catalog.py`)

`SCHEMA_CATALOG: dict[str, type[KernelModel]]` maps each schema ID to a payload model.
`validate_payload(schema_id, data) -> KernelModel` raises `UnknownSchemaError` or
`PayloadValidationError`. `export_json_schemas(dir)` writes
`kernel/schemas/<id>.schema.json`, and a test asserts the committed files match.
Fixtures live in `tests/kernel/fixtures/{valid,invalid}/<id>/*.json`.

| Schema ID | Payload fields |
|---|---|
| `leafcutter.goal_request.v1` | `goal`, `context_summary` |
| `leafcutter.decision_request.v1` | `question`, `options: list[Option]`, `criteria: list[Criterion]`, `criteria_missing: bool`, `evidence_ids`, `constraint_ids`, `approval_required: bool`, `decision_scope` |
| `leafcutter.decision_report.v1` | `status`, `recommendation`, `selected_option_id`, `criterion_assessments`, `supporting_evidence_ids`, `contradicting_evidence_ids`, `open_questions`, `approval_status`, `limitations`, `rationale`, `trace_refs` |
| `leafcutter.research_request.v1` | `question`, `evidence_needs`, `source_restrictions`, `existing_evidence_ids`, `expected_coverage` (all_required or best_effort) |
| `leafcutter.retrieval_request.v1` | `need: EvidenceNeed`, `source_ids`, `detail` (excerpt), `limits` (`top_k`, `max_chars`) |
| `leafcutter.evidence_bundle.v1` | `EvidenceBundle` plus inline `evidence` and `findings` |
| `leafcutter.options_request.v1` | `problem`, `constraint_ids`, `existing_option_ids`, `evidence_ids`, `max_options`, `propose_criteria: bool` |
| `leafcutter.options.v1` | `options` (every one has `proposal_status=proposed`), `proposed_criteria`, `unresolved_feasibility` |
| `leafcutter.synthesis_request.v1` | `operation`, `question`, `evidence_ids`, `output_requirements`, `limits` |
| `leafcutter.findings.v1` | `findings`, `agreements`, `disagreements`, `constraints`, `assumptions`, `unknowns` |
| `leafcutter.human_question_request.v1` | `question`, `choices`, `free_text_allowed`, `why_research_cannot_settle`, `decision_id` |
| `leafcutter.human_answer.v1` | `choice_id`, `free_text` (exactly one is set) |

Semantic checks run after schema checks:

- Cited evidence IDs exist.
- A selected option was supplied.
- A human answer's `choice_id` is one of the offered choices.

## Capability registry (new, starts empty)

The decision is recorded in
[ADR-055](../architecture/adrs/ADR-055-capability-registry-starts-empty.md).
`config/capability_registry.json` follows the draft-07 convention of its siblings
`config/agent_registry.json` and `config/skill_registry.json`:

```json
{ "$schema": "./capability_registry.schema.json",
  "_comment": "Kernel-routable capabilities only. Legacy registries are never read.",
  "registry_id": "leafcutter.capabilities", "registry_version": 1, "capabilities": [] }
```

Entry shape (`config/capability_registry.schema.json`, `additionalProperties: false`,
`capabilities` has `minItems: 0`):

| Field | Rule |
|---|---|
| `id` | `^[a-z][a-z0-9._-]*$`, e.g. `decision`, `research`, `retrieve.repository`, `host.synthesize` |
| `name`, `description` | `description` is the trusted Jev routing criterion text (≤ 400 chars) |
| `version` | semver; must equal the version registered in the binding table |
| `request_kinds`, `operations` | RequestKind values; operation names |
| `accepts_schemas`, `produces_schemas` | Catalog IDs only |
| `scope_tags`, `components` | Empty means any scope; component ids come from `docs/components.json` |
| `execution_mode` | `native` or `host_handoff` |
| `binding` | Key into the trusted `BindingTable`. It is never an import path. |
| `side_effect_class`, `permissions_required` | SideEffectClass; e.g. `["read_repo"]` |
| `enabled`, `availability` | `availability`: `{status: available, unavailable or experimental; reason}` |
| `routing` | `semantic` (offered to Jev) or `fixed` (bound deterministically; never shown to Jev) |
| `cost_hints` | `{jev_calls, host_operations, latency_ms}`; any value may be null |
| `admission` | Required. `{kind: native_registration or legacy_admission, decision_ref, admitted_on, admitted_by, legacy_source}`. `legacy_admission` requires `legacy_source: {registry, id}` and a `decision_ref` matching `^ADR-\d{3}$`. There is no bulk import path. |

P5 adds these entries with `native_registration` and `decision_ref: TICKET-20260930-KernelBootstrapV0`:

- `decision` (native, semantic)
- `research` (native, semantic)
- `retrieve.repository` (native, fixed)
- `host.generate_options`, `host.synthesize`, `host.research`, `host.formulate_question` (host_handoff, all `fixed`). As built, `host.research` accepts only `retrieval_request.v1` (operation `bounded_research`); it is not a semantic capability. The free-form `research_request.v1` goes to the native `research` capability.

## Registry adapter and eligibility (`registry/`)

- **`load_registry(path) -> RegistrySnapshot`**.
  - Validates the file with jsonschema, then with Pydantic.
  - `RegistrySnapshot` fields: `registry_id`, `registry_version`, `content_hash` (sha256 of the canonical JSON), `source_path`, `loaded_at`, `descriptors: tuple[CapabilityDescriptor, …]`.
  - On failure it raises `RegistryError`.
- **`BindingTable`** (`bindings.py`).
  - Methods: `register(key, version, factory)`, `resolve(key, version) -> CapabilityExecutor` (raises `BindingUnavailable`), and `keys()`.
  - Only the composition root (`bootstrap.py`, P7) and tests populate it.
- **`filter_candidates(request, snapshot, bindings, run_permissions, budgets, cfg, *, scope=None, operation=None) -> EligibilityReport`** (pure).
  - `operation` (the scheduler passes `request.operation`) keeps a candidate only if the operation is in its `operations`. Without it, `retrieve.repository` and `host.research` (both accept `retrieval_request.v1`, both `fixed`) tie on the lowest id. The research capability sets `operation` on each retrieval child (`retrieve` or `bounded_research`); no resolver hook exists.
  - Checks run in this order, and each exclusion records a reason code:
    1. `disabled`
    2. `unavailable:<reason>`
    3. `binding_missing`
    4. `kind_mismatch`
    5. `payload_schema_mismatch`
    6. `output_schema_mismatch`
    7. `scope_mismatch`
    8. `permission_denied`
    9. `side_effect_forbidden` (MVP allows only `none`, `read_only`, `run_artifacts`)
    10. `budget_exhausted`
  - `outcome_hint`:
    - `no_match` when nothing matched kind and schema.
    - `unavailable` when every match was excluded by checks 1–3 or 8–10.
    - `selected` (deterministic binding, no Jev call) when exactly one candidate is eligible and the request kind is not `capability`.
    - `needs_semantic` when the request kind is `capability` (the root goal and any free-form request), or when more than one candidate is eligible. Only these requests go to Jev. `fixed` descriptors are never offered to Jev; if only `fixed` candidates remain, the lowest id is selected deterministically and the tie is logged.

## Configuration (`config/kernel_config.default.json`, `config.py`)

`load_kernel_config(override: Path | None) -> KernelConfig` reads the defaults, deep-merges an
optional override (`--config` or the env var `LEAFCUTTER_KERNEL_CONFIG`), and validates with
Pydantic. `config/kernel_config.schema.json` is generated from the model, and a test asserts it
matches. Node code never hard-codes a threshold: every value below comes from this file and is
recorded in traces.

| Section | Keys and defaults |
|---|---|
| `paths` | `run_root: ".leafcutter/kernel"`, `registry: "config/capability_registry.json"` |
| `limits` (§13.2) | `max_work_items 32`, `max_depth 4`, `max_concurrent_native 4`, `max_concurrent_host 1`, `max_retries 2`, `no_progress_limit 2`, `max_jev_calls 40`, `max_host_operations 8`, `max_active_seconds 300`, `max_cost_usd null`, `capability_timeout_seconds 120`, `langgraph_recursion_limit 500`, `max_scheduler_iterations null` (null: derived from the recursion limit; `KernelRuntime.max_scheduler_iterations` overrides it) |
| `routing` | `min_selected_probability 0.8`, `min_confidence 0.5`, `on_insufficient_context "human"` |
| `decision` | `sufficiency_threshold 0.8`, `satisfies_threshold 0.8`, `preference_threshold 0.7`, `conflict_threshold 0.7`, `missing_min_probability 0.4` |
| `research` | `need_required_threshold 0.8`, `need_supporting_threshold 0.5`, `evaluable_threshold 0.7`, `allow_synthesis true`, `category_descriptions {…6 entries…}` |
| `retrieval` | `relevance_threshold 0.5`, `top_k 6`, `max_candidates 20`, `excerpt_context_lines 12`, `max_excerpt_chars 2000`, `max_file_bytes 400000`, `deny_globs [".env*","**/*.pem","**/*.key",".security-allowlist","**/.git/**"]` |
| `sources` | A list of `{id, kind: repo_text, knowledge_map or host_research, categories, roots or surfaces}`. Defaults are listed in part 4. Category names never contain vendor names. |
| `jev` | `model "jev-latest"`, `transport "classifier"` (or `http`; `TypeSafeJevAdapter.from_config` reads it), `timeout_seconds 30`, `max_questions_per_call 20`, `max_state_chars 60000`, `retry_backoff_seconds 1.0`, `price_per_input_token_usd 4.2e-8` (estimate; provenance `estimated`) |
| `host` | `enabled true`, `fallback_on_no_match true`, `max_repair_attempts 1`, `formulate_questions false`, `max_input_chars 60000` |
| `data_policy` | `send_repo_excerpts_to_jev true`, `telemetry_excerpts "truncated"` (truncated, hash or none), `telemetry_max_field_chars 4000` |
| `langfuse` | `enabled true`, `environment "development"`, `trace_name "leafcutter-run"`, `flush_on_exit true` |

## Secrets (`secrets.py`)

`load_secrets(env_file: Path | None) -> SecretSettings` works as follows:

- **Fields:**
  - `jev_api_key: SecretStr | None`
  - `langfuse_public_key: str | None`
  - `langfuse_secret_key: SecretStr | None`
  - `langfuse_base_url: str | None`
  - `origins: dict[str, str]`, recording `env` or the path of the `.env` file for each value
- **Lookup order:**
  1. The process environment.
  2. The explicit `--env-file` or `LEAFCUTTER_ENV_FILE`.
  3. The first `.env` found walking up from the repository root. This finds
     `C:\Users\Hendrik\Code\leafcutter\.env` from both the main checkout and every worktree.
- **Names:**
  - `JEV_API_KEY`, with alias `TYPESAFE_API_KEY`.
  - `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`.
  - `LANGFUSE_BASE_URL`, with fallback `LANGFUSE_HOST`. SDK 4.16 still reads `LANGFUSE_HOST` as a deprecated alias.
- **Parsing:** the same as `judge.py`. It accepts an `export ` prefix and strips quotes.
- **Safety:**
  - It never mutates `os.environ` and never logs values.
  - `describe()` returns presence booleans only.
  - Missing Jev credentials make the run fail with `provider_unavailable`, never with a gap.
  - Missing Langfuse credentials mark observability as `degraded`.

## As built (decision store)

- **Contracts.** `Decision` gains `approved_at` (UTC, set when the human approves; null otherwise) and `precedent_ids` (earlier decisions used as evidence). `EvidenceBundlePayload` gains `need_evidence` (per need, the evidence that passed relevance) and `need_limitations` (per need, the retrieval cut notes); both default empty, and the committed JSON Schema is regenerated.
- **Config.** A `memory` section (`kernel/config_memory.py`, held by `KernelConfig.memory`): `backend` (`file` default, or `null`), `repository_id`, `decisions_dir`, `max_precedents`, `min_candidate_score`, `applies_threshold` (0.5), `reuse_threshold` (0.8, never below the first) and `criterion_evidence_max` / `criterion_evidence_min_overlap` (evidence cited per criterion). `config/decision_record.schema.json` is generated from `kernel/memory/models.py` like the config schema, and a test keeps it in sync.
- **Registry.** The `decision` capability's `side_effect_class` is `run_artifacts` (it stages a record in the run root); it still never writes the repository.
- **Record.** One YAML file per approved decision in `docs/decisions/`, id `dec-<16hex>`, flat filter fields (so the stdlib knowledge-map parser reads id, title and component edges), nested options, criteria, evidence references, assessment, approval, provenance and append-only corrections. See ADR-059, ADR-060 and ADR-061.
