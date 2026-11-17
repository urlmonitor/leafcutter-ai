---
title: "Reference: Knowledge Retrieval Answers"
description: "Request fields, status meanings, population rules, evidence assessment, evaluation contracts and explicit limits for repository research answers."
type: reference
status: active
created: '2026-10-01'
last_updated: '2026-10-09'
components:
  - knowledge_management
  - decision_kernel
related_docs:
  - docs/reference/knowledge-retrieval-evidence.md
  - docs/how-to/run-knowledge-retrieval.md
  - docs/architecture/components/knowledge-retrieval.md
  - docs/architecture/adrs/ADR-062-standalone-knowledge-retrieval.md
  - docs/analysis/2026-10-01-repository-query-catalog.md
  - docs/analysis/2026-10-01-repository-query-evaluation-cases.json
---
# Knowledge Retrieval Answers

This reference defines the neutral research-answer fields and their evidence limits for people, agents and the existing kernel integration.

---

## Public surfaces

| Surface | Method | Description |
|---|---|---|
| `python -m knowledge retrieve --request FILE --repository-id ID` | JSON request | The command executes an authorized registered query through the neutral retrieval port. |
| `KnowledgeService.retrieve(request)` | Async Python | The port returns execution state, disclosed evidence and optional question and supplied-evidence assessments. |
| `python -m knowledge assess --request FILE --repository-id ID` | JSON packet | The command assesses supplied attributable content; it performs no repository discovery, test execution or source inspection. |
| `knowledge.assessments.assess(payload, retrieval=None, manifest=None)` | Python | The public consumer accepts actual final retrieval and manifest inputs from application composition. |
| `python -m knowledge evaluate --cases FILE --repository-id ID` | JSON cases | The command executes reviewed requests or supplied assessments before applying separate expected predicates. |
| `python -m knowledge compare --baseline FILE --proposal FILE [--gates FILE]` | JSON reports | The command compares measured reports under explicitly chosen gates; it never activates a query. |

The [how-to](../how-to/run-knowledge-retrieval.md) contains configuration, synchronization and observability procedures. Ordinary research decisions remain in the existing LangGraph/Jev integration. [ADR-064](../architecture/adrs/ADR-064-persona-discovery-before-feature-planning.md) records planning policy only; this feature adds no planning workflow implementation.

## Distinct status meanings

| Field | Type | Default | Meaning |
|---|---|---|---|
| Canonical `status` | Canonical enum | No synthesized value | The field records the AC lifecycle, such as `active`; it does not report completed implementation. |
| Canonical `req_status` | Canonical enum | No synthesized value | The field records the requirement lifecycle. |
| Canonical `work_status` | Canonical enum | No synthesized value | The field records implementation progress, including the source values `todo` and `done`. |
| Canonical `readiness` | Canonical enum | No synthesized value | The field records requirement readiness; it does not establish deployment or executed proof. |
| Canonical `priority` | Canonical value | No synthesized value | The field records product priority and does not become a computed ranking. |
| Retrieval `status` | Enum | Computed | Allowed values are `ok`, `partial`, `disabled`, `unavailable`, `unsupported`, `stale` and `error`. The field describes query execution. |
| `answer.status` | Enum or null | `null` without requirements | Allowed values are `fulfilled`, `partial` and `unresolved`. The field describes whether actual evidence supplies the required facts and scope. |
| Assessment `status` | Kind-specific enum | Computed | The field describes a conditional interpretation; capability fitness uses its own gap classifications. |
| Observation `state` | Enum | `disabled` | Allowed values are `disabled`, `unavailable`, `unverified` and `verified`. The field describes observation delivery/verification. |

Canonical enum definitions remain in [AC schema](ac-schema.md). For example, `status=active`, `work_status=todo`, `readiness=approved` and retrieval `status=ok` can all describe the same record without contradiction. Missing `work_status` makes a question requiring that field incomplete even when the query succeeds.

## Retrieval request

| Field | Type | Default | Description |
|---|---|---|---|
| `contract_version` | String | `"1"` | The transport contract version remains compatible with existing requests. |
| `request_id` | String | Required | The caller supplies a bounded request identity. |
| `repository_id` | String | Required | The field must match configured authorized repository scope. |
| `operation` | String | `get_entities` | The value identifies a builtin or trusted catalog operation. |
| `operation_version` | String | `"1"` | The value selects a retained operation version. |
| `operation_digest` | String or null | `null` | A custom operation requires its verified catalog digest; builtins accept `null` or `builtin:1`. |
| `mode` | Enum | `exact` | Allowed values are `exact`, `graph`, `semantic`, `hybrid` and `precedent`, subject to the registered operation. |
| `arguments` | Object | `{}` | Only arguments registered for the selected operation are accepted. |
| `revision` | String | `latest` | The value is `latest` or an exact 40-character Git SHA. Actual source SHA and generation are returned separately. |
| `disclosure_level` | Integer | `0` | Levels 0â€“3 select identity/metadata, structural context, summary, and bounded source content. |
| `budget` | Object | See below | All work and whole-response limits remain bounded. |
| `continuation` | String or null | `null` | The authenticated continuation binds operation, scope, requirements, assessment and cumulative budgets. |
| `allow_stale` | Boolean | `false` | Stale evidence requires explicit permission and retains its actual source identity. |
| `correlation` | String map | `{}` | Caller correlation identifiers do not change retrieval semantics. |
| `answer_requirements` | Object or null | `null` | The object preserves the original question, required facts and population policy. |
| `assessment` | Object or null | `null` | An explicit supplied-evidence packet is assessed against final actual disclosed evidence. Its repository must match the request. |

| Budget field | Type | Default | Description |
|---|---|---|---|
| `max_results` | Integer | `20` | The returned evidence limit is 1â€“100. |
| `max_candidates` | Integer | `50` | The cumulative work limit is 1â€“200, including traversal work. |
| `max_neighbors_per_seed` | Integer | `10` | The per-seed expansion limit is 1â€“50. |
| `max_hops` | Integer | `2` | The traversal depth is 0â€“2. |
| `max_rounds` | Integer | `3` | The continuation limit is 1â€“10. |
| `max_content_bytes` | Integer | `32768` | The whole-response allowance is 1024â€“131072 bytes. |
| `max_estimated_tokens` | Integer | `4000` | The token allowance is 256â€“16000 using the documented UTF-8 byte estimator. |
| `deadline_ms` | Integer | `10000` | The cumulative deadline is 1â€“30000 milliseconds. |

## Answer requirements and assessment

| Field | Type | Default | Description |
|---|---|---|---|
| `answer_requirements.original_question` | String | Required | The unchanged original question is retained, with a 4000-character maximum. |
| `answer_requirements.required_fields` | String list | `[]` | Up to 32 distinct exact field names are required; `canonical_id` is the identity name, not `id`. |
| `answer_requirements.scope.entity_ids` | String list | `[]` | Up to 64 original canonical target IDs, each 1–200 characters, remain required independently of query arguments; public single-entity and selected-entities interpretations populate them before selection. |
| `answer_requirements.require_complete` | Boolean | `true` | The flag requires exhaustive enumeration; disabling it cannot supply absent execution, missing identities, unresolved scope or a complete truncated criterion. |
| `answer_requirements.scope.population` | Enum | `returned_entities` | Allowed values are `returned_entities`, `ac_descendants` and `declared_dependents`. |
| `answer_requirements.scope.root_id` | String or null | `null` | The root identifies the requested population and must match the operation arguments. |
| `answer_requirements.scope.levels` | List or null | `null` | Explicit `[]` selects all levels; a list selects `L0`â€“`L3`; `null` leaves hierarchy level selection unresolved. |
| `answer_requirements.scope.inclusion` | Enum or null | `null` | Allowed resolved hierarchy rules are `root_excluded`, `terminal_leaves` and `include_root`; omission does not choose one. |
| `answer.original_question`, `required_fields`, `scope` | Preserved values | From request | These fields identify the assessed question rather than a replacement question inferred from returned rows. |
| `answer.missing_fields` | Object list | `[]` | Each entry contains `canonical_id`, `field` and attributable `reason`. |
| `answer.completeness.complete` | Boolean | Computed | The value is true only when the requested enumeration and source scope are established. |
| `answer.completeness.known_count` | Integer | Computed | The value counts unique actually disclosed entities. |
| `answer.completeness.exact_total` | Integer or null | `null` unless complete | A truncated or unestablished population has no exact total. |
| `answer.completeness.limitations` | String list | `[]` | The list records enumeration and source-scope limits. |
| `answer.work_status_counts` | Count map or null | `null` | A requested complete breakdown appears only when enumeration is complete and all counted work statuses are known. |
| `answer.known_work_status_counts` | Count map | `{}` | A requested subset breakdown includes an `unknown` bucket when needed. |
| `answer.limitations` | String list | `[]` | The list records non-fulfilled question conditions. |

`answer.scope.entity_ids` echoes these original obligations. For example, `{"population":"returned_entities","entity_ids":["KM-500c-1","KM-500c-2"]}` requires evidence for both identities even if a builtin or saved query returns only one. Missing targets keep fulfillment partial and `exact_total=null`. Descendant and relationship requests leave this list empty because their seed is not itself a required returned member; their declared population policy still applies.

A representative partial answer is `{"status":"partial","completeness":{"complete":false,"known_count":4,"exact_total":null},"work_status_counts":null}`. This fragment is an answer object, not a new retrieval request or an executed result.

## Field provenance and availability

See [Knowledge Retrieval Evidence](knowledge-retrieval-evidence.md) for the complete
field contract, canonical provenance, requested source excerpts and unavailable or
truncated outcomes. It distinguishes default criteria disclosure from separately
cited requested fields while retaining the same source and caller budgets.

## Population operations

| Operation | Mode and arguments | Population contract |
|---|---|---|
| `get_entities` | `exact`, `{"entity_ids":["KM-500c-2"]}` | The query retrieves named identities and does not establish a global inventory. |
| `get_ac_descendants` | `graph`, `{"root_id":"TQ-500f"}` | The query follows canonical structural-parent relationships with explicit levels and inclusion. A vague topic or omitted inclusion requires clarification. |
| `get_declared_dependents` | `graph`, `{"entity_ids":["TQ-500f-2"]}` | The query retrieves direct incoming `depends_on` declarations. Each result carries its own supporting edge; it does not establish transitive or code-consumer impact. |

At source `9d11594782abfb417d0f3a826bfb1f91f3a523ac`, the explicit `TQ-500f` L2/L3 scope has 15 descendants when only the selected root is excluded, with five `done` and ten `todo`; terminal-leaf selection has 11. These are pinned example values, not repository-wide totals or promises about `latest`. A default response budget can disclose fewer rows and correctly leave the exact total unknown.

```json
{
  "request_id": "tq-work-status",
  "repository_id": "leafcutter",
  "revision": "9d11594782abfb417d0f3a826bfb1f91f3a523ac",
  "operation": "get_ac_descendants",
  "mode": "graph",
  "arguments": {"root_id": "TQ-500f"},
  "disclosure_level": 1,
  "budget": {"max_results": 100, "max_candidates": 100, "max_content_bytes": 131072, "max_estimated_tokens": 16000},
  "answer_requirements": {
    "original_question": "How many TQ-500f descendants are done or todo, excluding only the root?",
    "required_fields": ["canonical_id", "work_status", "level"],
    "scope": {"population": "ac_descendants", "root_id": "TQ-500f", "levels": ["L2", "L3"], "inclusion": "root_excluded"},
    "require_complete": true
  }
}
```

`stats.population` records actual population, root, levels, inclusion, relation, direction, completeness and applicable depth. Candidate, fanout, depth, response or continuation limits prevent an exact total. Zero rows with an unresolved root or unavailable source are not proof of an empty population. Every continuation response contains one page, including the final page. Its `known_count` and known status breakdown describe that page; `exact_total` remains null and the complete-answer assessment remains partial unless the caller separately establishes an aggregate. The service does not turn a final five-row page into a five-record global count.

## Query fitness

| Classification | Meaning | Query-only build eligibility |
|---|---|---|
| `supported` | A matching operation and required source mappings are established. | The existing operation is used. |
| `missing_query` | Required kinds, relationships and fields are mapped, the authorized catalog search is complete, and no matching operation exists. | The value is true, subject to existing separate build/admission authorization. |
| `unsupported_mapping` | A required source kind or relationship is unsupported. | The value is false. |
| `field_availability_gap` | A required field has no established mapping. | The value is false. |
| `unknown` | The source pin, mapping metadata or catalog search is not established. | The value is false. |

The public helper accepts a pinned manifest, `required_kinds`, `required_relationships`, `required_fields` grouped by kind, `matching_operation` and `catalog_complete`. For `assess`, these required vocabularies occupy `requirements`; matching operation and catalog completeness can be top-level. Conflicting duplicated values are rejected.

```json
{
  "kind": "capability_fit", "repository_id": "leafcutter",
  "source_sha": "9d11594782abfb417d0f3a826bfb1f91f3a523ac",
  "manifest": {}, "evidence": [],
  "requirements": {"required_kinds": ["AcceptanceCriterion", "Test"], "required_relationships": ["covered_by"], "required_fields": {"Test": ["canonical_id"]}},
  "matching_operation": null, "catalog_complete": true
}
```

The empty-manifest example returns `unknown` and cannot authorize a builder. Actual query growth uses trusted pinned metadata, not a supplied positive readiness boolean.

## Supplied evidence assessments

| Common field | Type | Default | Description |
|---|---|---|---|
| `kind` | Enum | Required | Supported kinds are `verification`, `readiness`, `implementation`, `regression`, `capability_fit`, `impact` and `clause_comparison`. |
| `repository_id`, `source_sha` | Strings | Required | The packet identifies authorized repository and immutable source scope. |
| `evidence` | Object list | `[]` | Up to 100 supplied content items fit within the 131072-byte packet limit. Each item has `evidence_id`, `kind`, `source` and nonempty `content`. |
| `declarations` | String list | `[]` | Standalone declarations are explicitly supplied. On the retrieval path, actual disclosed canonical references replace this list. |
| `discovery` | Output string | Computed | The output distinguishes a supplied packet from actual disclosed declarations. |
| `evidence_basis` | Output string | Computed | The output states that attribution does not independently verify source provenance. |
| `limitations` | Output list | `[]` | Unsupported content, foreign scope and missing support remain explicit. |

| Kind | Additional input | Output and limit |
|---|---|---|
| `verification` | `execution_receipt` content contains supported JSON fields or explicitly reviewed literal quoted claims. | `declared_references`, `receipts`, `executed_proof=reported|unverified` and `independent_execution_verified=false` distinguish references, historical reports and verified execution. |
| `readiness` | Attributable `policy` content defines `id`, nonempty equality `clauses` with `id/field/equals`, optional deployment requirement/environment; standalone candidate JSON is separately labeled. | `recommendations` retain canonical facts from actual retrieval, clause outcomes, inferred readiness and unverified/reported deployment. Missing policy produces an unresolved result. Packet facts never overwrite actual canonical facts. |
| `implementation` | `stages` contain name, evidence ID and exact quote in supplied source content; optional runtime diagnostic content carries matching request/attempt/source IDs. | `stages` are labeled interpretations; `runtime_cause` remains null without matching diagnostics; `complete_code_graph=false`. |
| `regression` | `inspections` identify test, behavior, evidence/quote, seeded facts, expected result, comparison case and actual/simulated boundaries. | Recommendations retain source quotes and `design_gaps`; missing negative controls remain gaps; `exhaustive=false` and `minimal=false`. |
| `capability_fit` | Manifest and explicit requirements use the preceding fitness contract. | Mapping gaps remain distinct from a missing query. Supplied manifests are not independently fetched by assessment. |
| `impact` | `before` and `after` contain actual serialized direct-dependency retrieval outputs. | Both source revisions remain visible. `added/removed` are null without two complete matching scopes and declaration provenance; `complete_code_impact=false`. |
| `clause_comparison` | Up to 32 `clauses` contain `clause_id`, `evidence_id` and an exact `quote` in scoped supplied content. Optional `interpretation` contains `relation` (`conflict`, `duplicate` or `uncertain`), at least two distinct supported `clause_ids`, and a nonempty `rationale` of up to 4000 characters. | Each retained clause keeps its literal quote and source locator. A supported proposal is labeled `inferred=true`, `authoritative=false`; `equivalence_established=false` and `authoritative_clause_id=null` always. Similarity alone produces no interpretation. Missing support leaves the result unresolved. |

Clause comparison records an explicitly supplied candidate interpretation; it performs no automatic duplicate search or conflict mining and never rewrites a canonical clause. Source attribution has the same supplied-evidence verification limits as the other assessment kinds.

A JSON execution report requires `tested_sha`, `run_id`, `environment`, `actor`, `execution_status`, `research_fulfillment` and `test_ids`. Optional deployment and artifact fields remain reported claims. A reviewed Markdown report supplies `reviewed_by` plus `claims`, each containing a `value` literally present in an exact `quote` from its content. Required quoted identities are tested SHA, environment, actor, execution state and research fulfillment. Unrecorded run IDs remain null. Unsupported unparsed report text remains unverified.

```json
{
  "kind": "verification",
  "repository_id": "leafcutter",
  "source_sha": "9d11594782abfb417d0f3a826bfb1f91f3a523ac",
  "declarations": ["tests/example.py::test_behavior"],
  "evidence": []
}
```

This declaration-only example produces `executed_proof=unverified`, not a passing test claim. The historical query-growth report stores a source SHA different from its tested SHA, states that Jev was scripted and the candidate BA-authored, and reports partial research. Its observed phrases remain historical supplied evidence; they do not become a current live-provider or deployment result.

## Observation and diagnosis

| Field | Type | Default | Description |
|---|---|---|---|
| `observation.state` | Enum | `disabled` | The state is independent from query execution and question fulfillment. |
| `trace_id` | String or null | Absent | A local identity alone does not verify remote visibility. |
| `trace_url` | String or null | Absent | A reference is returned only when established by the caller-owned remote verification boundary. |
| `reason` | String or null | Absent | A bounded explanation describes delivery or verification limitations. |
| `request_id`, `retrieval_id` | Strings or absent | Caller-bound | Correlation identifies the actual finalized attempt. |

The neutral service invokes its injected observer once after final evidence and answer budgeting. Observer failure preserves the actual retrieval and does not repeat it. Without an observer the state is `disabled`. Successful local delivery remains `unverified` without matching remote evidence. Missing traces cannot establish a runtime cause. Source interpretation and runtime diagnosis remain separate evidence categories.

## Evaluation and comparison

| Field | Type | Default | Description |
|---|---|---|---|
| `evaluation_version` | String | Legacy list uses `1` | A rich object requires `"2"`; the original planned specification is not implicitly executable. |
| `reviewed_by`, `source_sha` | Review metadata | Required review; explicit scope | The pack records reviewed expected outcomes separately from actual output. |
| `cases[].state` | Enum | `runnable` | `planned` and `not_run` do not execute or pass. |
| `cases[].request` | Retrieval object | One execution input | The request uses the same builtin or trusted custom-catalog validation as research. |
| `cases[].assessment` | Assessment packet | Alternative execution input | The evaluator invokes the actual public assessment consumer; it does not fabricate retrieval quality metrics. |
| `cases[].assertions` | Predicate list | `[]` | Supported dotted-path predicates are `equals`, `contains`, `set_equals` and `absent`. No assertions means no passing rich verdict. |
| `cases[].relevant_ids`, `correction_ids` | Reviewed lists | `[]` | These fields provide legacy entity-ID relevance expectations. |
| `actual`, `expected`, `judgments` | Output objects | Measured | Actual fields are recorded before expected values are consulted; missing values are never filled from the oracle. |
| `specification_state`, `execution_state`, `verdict` | Output states | Measured | `executed` is distinct from `passed`, `failed` and `not_run`. |
| `denominators` | Count object | Measured | Total, executed, passed, failed and not-run counts remain explicit. |
| Quality and timing fields | Numbers or null | Measured | Incomplete/unavailable retrieval has no perfect-empty quality score. Retrieval timing and `end_to_end_ms` remain separately recorded. |
| `review_fingerprint`, `answer_semantics_version`, `implementation_digest` | Version identities | Recorded | Changed case judgments, source, field meaning, mapping or query scope invalidate affected comparisons until reviewed. |
| `coverage` | Object | `{}` | Sample families, uncovered origins and representative-benchmark limitations are explicit. |

```json
{
  "evaluation_version": "2", "reviewed_by": "independent source review",
  "source_sha": "9d11594782abfb417d0f3a826bfb1f91f3a523ac",
  "cases": [{"id": "future-live-provider", "state": "not_run", "reason": "Live provider evidence has not been collected."}]
}
```

This example has one not-run case and zero passing cases. The [original twelve-case plan](../analysis/2026-10-01-repository-query-evaluation-cases.json), [reviewed executable adaptation](../analysis/2026-10-01-repository-query-evaluation-runnable.json), and separately recorded execution report are distinct artifacts. Twelve cases sample six of eight families and do not constitute a representative benchmark of all 25 questions. Real-provider and deployment proof remain pending unless a separate actual report establishes them.

Comparison gates contain `baseline_review_fingerprint`, `min_pass_rate`, `max_p95_latency_ms` and `min_executed_cases`. Missing gates return `not_run`; incompatible reviewed scope returns `invalidated`. An explicitly reviewed implementation change is separately declared when needed. Gates report measured outcomes and explicit denominators; passing a nonrepresentative sample remains `limited` for promotion. Comparison causes no query activation, canonical rewrite, autonomous optimizer or model-weight training.

## Query-family and role-question coverage

The origin IDs and examples remain authoritative in the [discovery catalog](../analysis/2026-10-01-repository-query-catalog.md); that document records the earlier inspected baseline rather than current implementation claims.

| Family | Origins | Current evidence contract and limit |
|---|---|---|
| RQ1 Inventory/status | BA-01 | Explicit resolved AC populations expose canonical work status and bounded complete counts; vague topic membership still requires clarification. |
| RQ2 Requirements/contracts | BA-02, BA-05, ITPO-01, CODER-02, QA-01 | Exact criteria and mapped ADR/source evidence are available; broad semantic contradiction search and unprojected test specifications require additional inspected evidence. |
| RQ3 Priority/readiness | PO-01, PO-02, PO-03 | Canonical priority/readiness/work status and explicit supplied policy support conditional recommendations; roadmap value ranking and deployment proof are not automatically available. |
| RQ4 Dependencies/impact | BA-03, PO-04, PO-05, ITPO-02, CODER-03 | Direct declared dependencies and two pinned-result comparison are supported; transitive code-consumer or benefit-impact completeness remains unverified. |
| RQ5 Implementation/field flow | CODER-01, CODER-05 | Supplied approved source quotes support bounded interpretation; complete call graphs and incident causes require separate evidence. |
| RQ6 Proof/regressions | BA-04, CODER-04, QA-02, QA-03, QA-04 | Declared test references, inspected fixture quotes and supplied historical receipts remain distinct; executed branch coverage and minimal regression sets are not inferred. |
| RQ7 Query fitness | ITPO-03 | Trusted manifest kinds/relationships/fields distinguish missing query from missing mapping before governed build selection. |
| RQ8 Runtime/diagnosis | ITPO-04, ITPO-05, QA-05 | Actual source/generation, failed-field assessment, observation state and matching diagnostic evidence remain attributable; no trace or deployment cause is invented. |

All 25 origins occur once in this mapping. Conditional source/fixture/readiness contracts are not automatic ingestion of those sources, and presence in the table does not claim every natural-language question was executed.

## Projection compatibility

Mapper `6` publishes a new immutable generation for the existing approved AC/ADR/component surfaces and declared file/test targets. Older generations do not gain fields by changing reader code. Existing publication and retention procedures remain authoritative; a failed build leaves the previous active generation unchanged. Source SHA, mapper version and generation identify distinct dimensions.

A manual synchronization is not evidence that a merge-triggered job ran. This change does not install a new automatic update schedule. Semantic mechanism capability does not imply generation `semantic_ready=true`. No live publication, provider call or remote trace verification is implied by this reference.

## See Also

- [Knowledge retrieval how-to](../how-to/run-knowledge-retrieval.md) - Configuration, synchronization and usage procedures.
- [Knowledge retrieval component](../architecture/components/knowledge-retrieval.md) - Existing ownership and integration boundaries.
- [ADR-062](../architecture/adrs/ADR-062-standalone-knowledge-retrieval.md) - Immutable standalone projection decision.
- [Repository query catalog](../analysis/2026-10-01-repository-query-catalog.md) - Original role questions and discovery limitations.
- [AC hierarchy](ac-id-hierarchy.md) - Canonical parent derivation and direct-child rules.
- `knowledge/contracts.py`, `knowledge/answer_models.py`, `knowledge/answers.py` - Neutral request, response and question-assessment contracts.
- `knowledge/populations.py`, `knowledge/capability_fit.py`, `knowledge/assessments.py` - Bounded population, source-fitness and supplied-evidence consumers.
- `knowledge/evaluation.py`, `knowledge/evaluation_comparison.py` - Actual-output grading and reviewed comparison gates.
