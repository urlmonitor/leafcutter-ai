---
title: How to run standalone knowledge indexing and retrieval
type: how-to
status: active
created: '2026-10-01'
components:
- knowledge_management
- decision_kernel
last_updated: '2026-10-09'
description: Run scoped repository queries and inspect answer completeness, evidence and observation delivery.
related_docs:
- docs/reference/neo4j-native-queries.md
- docs/reference/knowledge-retrieval-answers.md
- docs/architecture/adrs/ADR-062-standalone-knowledge-retrieval.md
- docs/architecture/components/knowledge-retrieval.md
- docs/how-to/kernel-query-growth.md
---
# How to run standalone knowledge indexing and retrieval

Run commands from the trusted Leafcutter checkout. Indexed Git objects are data, never executable parsers. Architecture and source rules: [ADR-062](../architecture/adrs/ADR-062-standalone-knowledge-retrieval.md), [Stage 0](../analysis/2026-10-01-knowledge-retrieval-stage0.md), [component](../architecture/components/knowledge-retrieval.md).

## Prerequisites

- Use the trusted checkout's Python environment and an authorized published Neo4j generation for live graph commands.
- Supply serving credentials outside request files; publication and catalog activation require separate existing authorization.
- Keep the repository identity, exact source revision and intended population explicit. A working-tree edit is not automatically published.
- Read [ADR-062](../architecture/adrs/ADR-062-standalone-knowledge-retrieval.md) and the [kernel query-growth guide](kernel-query-growth.md) before enabling kernel research.

## Steps

### Explore the graph in Aura

See the [native graph reference](../reference/neo4j-native-queries.md#explore-the-graph-in-aura)
for domain labels, saved Bloom views, current component filters and verified
native-query catalog replacement.

### Inspect complete native fields

See [native fields and refresh](../reference/neo4j-native-queries.md#inspect-complete-native-fields)
for authored properties, nested leaves, null/empty distinctions, publication
receipts and the explicit native-metadata refresh procedure.

### Step 1 - Check optional service availability

```sh
python -m knowledge capabilities
python -m pip install -r knowledge/requirements-neo4j.txt 'pydantic>=2,<3'
docker compose -f knowledge/compose.yaml up -d
```

The first command returns disabled without connecting to Neo4j or loading optional SDKs. Kernel defaults likewise preserve ordinary repository retrieval. Before Compose, set LEAFCUTTER_NEO4J_WRITER_PASSWORD through your environment. knowledge/.env.example lists nonsecret placeholders; it is not automatically loaded. Compose binds localhost ports 17474 and 17687 and pins the Neo4j 5.26 Community image digest. Verified development server: 5.26.31, Python driver6.0.3; other versions and Aura are not implied tested.

Serving uses LEAFCUTTER_NEO4J_URI, LEAFCUTTER_NEO4J_USERNAME and LEAFCUTTER_NEO4J_PASSWORD. Publication uses the same URI plus distinct LEAFCUTTER_NEO4J_WRITER_USERNAME and LEAFCUTTER_NEO4J_WRITER_PASSWORD. LEAFCUTTER_NEO4J_DATABASE defaults to neo4j. Use verified TLS remotely. Separate writer/serving privileges where the deployment supports them; the local Community administrator account does not prove read-only user enforcement. Never put secrets in request JSON. No arbitrary Cypher is exposed.

### Step 2 - Publish a validated immutable generation

```sh
python -m knowledge validate --root REPOSITORY --repository-id leafcutter --revision REVISION
python -m knowledge plan --root REPOSITORY --repository-id leafcutter --revision REVISION
python -m knowledge sync --root REPOSITORY --repository-id leafcutter --revision REVISION
python -m knowledge status --root REPOSITORY --repository-id leafcutter --revision REVISION
```

REPOSITORY is an absolute trusted checkout; REVISION is an exact commit SHA. Validation and plan do not connect or publish. Sync reads immutable Git objects, builds a full generation and atomically publishes after validation. Repeating the same revision/mapping reuses its generation. Failed builds leave the previous generation active; stale or non-descendant publications cannot silently replace it.

Standalone writer commands use a bounded **30-second transaction timeout** for staging and atomic publication; serving retains its independent **3-second default**. Node and relationship batches remain capped at 250, and count validation and publication guards still apply. A transaction-timeout error alone does not identify the slow statement. After an authorized retry, confirm the published SHA and lag before calling recovery successful; a local configuration test does not establish live publication.

Default imports include all reviewed native record types. Existing AC, ADR and
Component identities remain stable; additional kinds use kind-qualified native
identities to prevent collisions. Specialized and generated document views are
excluded from duplicate ingestion. SourceFile and Test remain explicitly referenced
paths rather than a whole-repository file scan. Required missing references fail
closed. Inspect the validation result for the exact revision you intend to publish.

For an isolated supported-surface demonstration:

```sh
python -m knowledge sync --root REPOSITORY --repository-id leafcutter-docs-demo --revision REVISION --surfaces adrs components
```

Projection scope is fingerprinted; changing surfaces through ordinary sync under an
existing published identity is rejected. Use the explicit native refresh for the
reviewed scope expansion. The separate demo identity cannot overwrite the full
repository projection. Decision records require the approved canonical source
contract; pending merge content is not published. Lesson/Policy stores and runtime
trace ingestion remain unsupported; synthetic history fixtures are labeled as such.

### Step 3 - Retrieve a bounded source-backed answer

Save this request as request.json, substituting the published repository and canonical ID:

```json
{"request_id":"manual-1","repository_id":"leafcutter","operation":"get_entities","mode":"exact","arguments":{"entity_ids":["KM-KGS-100a-3"]},"revision":"latest","disclosure_level":0,"budget":{"max_results":2,"max_content_bytes":8192,"max_estimated_tokens":2048}}
```

```sh
python -m knowledge retrieve --backend neo4j --repository-id leafcutter --root REPOSITORY --request request.json
```

Level0 discovers identity/title/provenance, level1 adds bounded relationships, level2 approved summaries/correction context, level3 a bounded excerpt read from the pinned SHA. Repeat with selected IDs and the returned source SHA. Source quotations preserve whitespace; summaries and derived graph context are labeled. Missing source returns explicit limitations. Read roots/deny rules apply at the kernel boundary.

Other registered graph operations include component context, acceptance criteria, related tests, relevant ADRs, policies and reviewed decision/correction/lesson/evidence relationships where mapped. Unsupported mappings return unsupported, never fabricated applicability. Exact absent IDs return ok with empty evidence; outages are unavailable, missing generations stale, invalid inputs structured errors. Inspect requested/executed mode, source SHA, generation, retrieval ID, warnings, truncated and continuation.

Resume a continuation with exactly the same repository, operation, arguments, revision, disclosure and budget, adding the returned continuation string. It stays pinned to the retained generation and consumes cumulative rounds/bytes/tokens/candidates/deadline. Changed inputs, tampering and expiration are rejected. Do not automatically exhaust every cursor. A continued page describes only the evidence returned on that page: reaching the final page does not establish an exact global total or fulfill the original whole-population question. Use one complete response within an authorized sufficient budget, or a separately verified aggregate that preserves scope, source pins and completeness. This implementation does not automatically aggregate pagination into an answer. Cancel, unavailable sources, unchanged evidence, adequate disclosure and exhausted budgets stop focused follow-ups.

### Step 4 - Configure the existing kernel retrieval binding

Set knowledge.backend=neo4j, trusted knowledge.repository_id and absolute knowledge.repository_root in kernel configuration. Add a source kind graph_query with its evidence categories; overrides replace source lists, so preserve other desired sources. A leafcutter.retrieval_request.v1 payload can include the optional knowledge operation/mode/arguments/disclosure object. Invocation and repository identity are bound by the composition root; backend sessions, queries and writer credentials do not enter kernel state.

The retrieve.repository binding consumes canonical Evidence/SourceVersion. Explicit low-level operation requests retain deterministic execution. Natural research carrying interpreted needs uses the shared finite Jev operation selector, with or without a query catalog; the earlier low-level compatibility helper does not bypass that selector. Compact discovery precedes selected-ID source disclosure. The existing research sufficiency judgment decides whether evidence answers the question. Similarity scores are ranking signals, never correctness probabilities.

Evidence IDs are stable for locator/content; retrieval IDs identify separate runs. Capability diagnostics and existing tracer record modes, SHA, generation and retrieval references. Graph provenance is explicitly derived context, source excerpts stay unchanged. Telemetry outages preserve retrieval with a warning. Async hosts await environment.aclose() before closing their loop; synchronous hosts call environment.shutdown() afterward. A synchronous shutdown inside a running loop is explicitly rejected.

### Step 5 - Evaluate the configured retrieval mode

Graph readiness is separate from vector readiness. Enable embeddings_enabled and set embedding_model, embedding_dimensions and endpoint/token environment-name settings. LEAFCUTTER_EMBEDDING_ENDPOINT is an explicitly configured HTTP gateway accepting POST JSON {model,texts} and returning {model,vectors}; it is not the OpenAI API protocol. Remote HTTPS is required; loopback HTTP is allowed for fixtures. No provider calls run unless enabled.

The ingestion API is knowledge.embedding_jobs.embed_snapshot(writer,snapshot,provider,cache={}); callers own persistent cache storage. Retrieval does not silently ingest. Changed text/model is ineligible until matching vectors exist. Standalone retrieve/evaluate accept --embeddings --embedding-model NAME --embedding-dimensions N. Missing or incompatible vectors return explicit readiness errors while graph retrieval remains available; no silent fallback is performed.

```sh
python -m knowledge evaluate --backend neo4j --repository-id leafcutter --root REPOSITORY --cases cases.json
```

Reviewed case fields are id, reviewed_by, synthetic, request, relevant_ids and correction_ids. Reports record revision/backend/model/query versions, precision/recall at k, correction coverage, provenance validity, bytes and latency. Deterministic vectors prove mechanics only and report semantic_usefulness_proven=false. Real-model evaluation is not run in this implementation session; a representative reviewed baseline and quality thresholds require that distinct evaluation.

### Step 6 - Inspect publication and recovery state

.github/workflows/knowledge-sync.yml activates only when KNOWLEDGE_SYNC_ENABLED=true and writer secrets are set. It handles canonical main pushes or explicit main-branch exact-SHA replay, verifies ancestry, serializes jobs and invokes standalone CLI. It is inactive on this feature branch until a later merge; no workflow run, push or merge was performed here. PR previews cannot publish canonical state.

```sh
python -m knowledge rollback --root REPOSITORY --repository-id leafcutter --generation-id RETAINED_GENERATION
python -m knowledge cleanup --root REPOSITORY --repository-id leafcutter --generation-id EXPIRED_GENERATION
```

Rollback selects a retained generation. Cleanup affects only the selected expired, non-active, projector-owned generation; foreign data is protected. Rebuild an empty authorized database from the same immutable revision/mapping and compare identities, edges/provenance; repeat sync for idempotence. Rebuild vectors with the same model and retained outputs where exact reproducibility matters.

Restore connectivity then replay a failed revision. Repair canonical reference errors in source before replay. Continue explicit graph requests during vector outage; never interpret unavailable semantic retrieval as no match. Inspect published SHA/status for lag and telemetry-loss diagnostics when trace export fails. Actual external merge execution, production memory mapping and real-model usefulness remain separately identified verification limits.

#### Aura environment compatibility

Serving accepts `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` as aliases for the default `LEAFCUTTER_NEO4J_*` names. Aura hosts ending in `.databases.neo4j.io` default to username `neo4j` when none is provided. `NEO4J_INSTANCE` is metadata, never a database name; database selection uses an explicit nonempty `database` setting first, otherwise `LEAFCUTTER_NEO4J_DATABASE` or `NEO4J_DATABASE` through the same source precedence, then `neo4j` as a fallback. The unset configuration default is `null`, so a saved Aura database is honored. Existing explicit database strings, including `neo4j`, continue to override environment values. Writer commands accept both database environment names.

Enabled serving and writer composition resolve each setting from the process environment, then the file named by `LEAFCUTTER_ENV_FILE`, then the nearest `.env` walking upward from the configured repository root (or current directory). Within a source, the legacy `LEAFCUTTER_*` name wins over its alias. Empty values count as absent, matching kernel credential loading. Custom configured variable names are exact: they do not fall back to conventional aliases. Named unreadable files fail; unreadable discovered files emit a generic warning. Loading never mutates the process environment and disabled serving never reads credential files.

An Aura instance ID and a Neo4j database name are different settings. For example,
`NEO4J_URI=neo4j+s://2fb38dda.databases.neo4j.io` selects the instance;
`NEO4J_DATABASE=neo4j` selects a database inside it. Use the actual database name
shown by your deployment. `NEO4J_INSTANCE=2fb38dda` does not select a database.
Setting the database to an instance ID fails unless a database with that exact
name exists. The local `.env` is not copied into GitHub Actions: the publication
workflow uses its configured database variable and writer secrets separately.

Keep the actual `.env` outside Git and set `LEAFCUTTER_ENV_FILE` to its existing path when a worktree cannot discover it. Do not copy credentials into the worktree. Writer operations accept the shared URI but still require `LEAFCUTTER_NEO4J_WRITER_USERNAME` and `LEAFCUTTER_NEO4J_WRITER_PASSWORD`; serving credentials do not silently authorize writes. Merely configuring Aura does not run migrations or index a corpus.

### Step 7 - Use the governed reusable query catalog

Set `knowledge.query_catalog_root` to an application-controlled directory outside prompt text. The catalog retains immutable descriptor and generated-Cypher versions plus their verification provenance. Only current native compiler entries are accepted; see the [saved-query replacement contract](../reference/neo4j-native-queries.md#saved-native-queries) when replacing an obsolete catalog. New operations require a trusted catalog context and a pinned digest; an unknown ordinary retrieval operation is still rejected.

```text
python -m knowledge catalog-list --catalog-root <directory>
python -m knowledge query-verify --catalog-root <directory> --repository-id <repository> --source-sha <exact-SHA> --candidate <candidate.json>
python -m knowledge query-register --catalog-root <directory> --repository-id <repository> --source-sha <exact-SHA> --candidate <candidate.json> --allow-catalog-write
python -m knowledge retrieve --backend neo4j --repository-id <repository> --catalog-root <directory> --request <request.json>
```

`query-verify` reads the configured Neo4j service and produces the reviewable compiled query and measured checks without activating it. `query-register` reruns those checks; it does not trust a supplied success receipt. Replacing an active operation requires a new version and `--expected-active-digest <previous-digest>`. Interrupted publication or conflicting writers leave the old catalog intact. A surviving `.activation.lock` after process termination requires an operator to establish that its writer is gone before removing that lock; the library does not guess that an active writer is stale.

The coding agent authors typed parameters, purpose, supported questions and a recipe with zero to two allowlisted directed relationship steps and optional property filters. The trusted compiler creates actual parameterized Cypher. It never executes caller-supplied Cypher or Python. Twenty input seeds, ten neighbors per step and bounded result limits keep expansion finite; transaction deadlines still apply. A one-item lookahead reports expansion saturation, including branches that later produce no evidence. Completed empty queries return `ok` with no evidence; saturated results return `partial` and identify the bound. Wider searches must refine their seeds or request an ordinary reviewed code extension.

The candidate includes positive and empty expected-result cases. The verifier executes those judgments against the exact pinned source and independently tests invalid input, bound injection and foreign scope. Passing these checks establishes declared-case conformance, not general semantic usefulness. The example [component test query](../../knowledge/examples/component_tests_candidate.json) joins component membership to acceptance-criterion test references in one new two-hop operation. Its expected IDs were independently reviewed against the commit named in [source judgments](../../reports/knowledge-query-growth-source-judgments.json).

The kernel's separate activation capability requires explicit `write_query_catalog` permission and the catalog-write effect. Read-only retrieval cannot acquire this permission through fallback. New research can discover admitted entries after restart; pinned requests select retained native entries; an explicit format replacement requires the new recorded digest and rejects the old pin. The original research still evaluates whether returned evidence answers its question. A successful build or admission is not an answer, and outage, denied access, unapproved source mapping and empty results remain distinct.

For a catalog intended to survive replacing or later merging an implementation worktree, configure a durable user/application data directory outside that worktree. The catalog contains query metadata and measured provenance rather than Neo4j credentials. Keep write access restricted to the activation owner; copying an untrusted catalog is not an authorization mechanism.


### Step 8 - Request the exact count population and required facts

Use the shared [answer contract reference](../reference/knowledge-retrieval-answers.md) for field, scope and proof meanings.

The new projected fields and hierarchy populations require publication with the updated committed mapper before an existing Aura deployment can serve them. Local Neo4j fixture proof is not an Aura upgrade. Complete the normal review/commit and authorized projection refresh first; inspect its published generation before using the example.

Save the following example as `count-request.json`, replacing `REVISION` with the exact published commit. It asks for all L2/L3 descendants, excluding only the named family root. It does not ask for terminal leaves alone.

```json
{
  "request_id": "test-writing-count-1",
  "repository_id": "leafcutter",
  "revision": "REVISION",
  "operation": "get_ac_descendants",
  "mode": "graph",
  "arguments": {"root_id": "TQ-500f"},
  "disclosure_level": 1,
  "budget": {"max_results": 100, "max_candidates": 100, "max_content_bytes": 131072, "max_estimated_tokens": 16000},
  "answer_requirements": {
    "original_question": "How many L2 and L3 test-writing ACs descend from TQ-500f, excluding only TQ-500f, and what are their work statuses?",
    "required_fields": ["work_status", "level"],
    "scope": {"population": "ac_descendants", "root_id": "TQ-500f", "levels": ["L2", "L3"], "inclusion": "root_excluded"},
    "require_complete": true
  }
}
```

```sh
python -m knowledge retrieve --backend neo4j --repository-id leafcutter --root REPOSITORY --request count-request.json
```

Inspect `answer.completeness.complete` and `exact_total` before quoting a total. `known_count` alone is not an exhaustive count. The independent source oracle at commit `9d11594782abfb417d0f3a826bfb1f91f3a523ac` contains **15** L2/L3 descendants when only TQ-500f is excluded, and **11** terminal leaves. Change `inclusion` to `terminal_leaves` only when the caller actually means to exclude every parent. The independent real Neo4j/public-service canary measured those totals with the explicit budget above; the root-excluded population had 5 done and 10 todo. That proof used the public Python service and actual Neo4j adapter/server, not a shell-CLI run or real Jev. These are source-pinned results, not timeless project totals; use the actual response for your run. A smaller result/content budget can make the answer incomplete even when every returned item is valid.

If execution `status` is `ok` but `answer.status` is `partial` or `unresolved`, inspect `answer.missing_fields`, `answer.limitations` and completeness. Lifecycle `status: active` cannot replace missing `work_status`. Do not compute done/todo counts from a truncated or undisclosed status field. Inspect the returned source SHA and field locators; source inspection used to construct an expected answer is separate from this tool run.

### Step 9 - Resolve an ambiguous research request through its existing continuation

Submit the original natural-language question through the configured kernel research entry described in [kernel query growth](kernel-query-growth.md). An optional `answer_requirements` contract may carry already explicit choices. Without it, the bounded Jev answer-contract node identifies requested facts and scope; it does not infer a root ID from a vague topic name.

For “exclude parent requirements,” answer the ordinary pending human interaction with the intended `scope.inclusion` (`root_excluded` or `terminal_leaves`) and any missing root, levels or `required_fields`. Use the existing `KernelService.resume_run` continuation with the original run ID; do not start a second question to simulate resumption. Established repository/revision and answer choices remain pinned. If whole-project enumeration is required but unsupported, report that limit or obtain a narrower authorized scope.

The retrieval LangGraph owns answer planning, clarification, readiness, source-fit checks, query selection, build waits and execution. A source-field/mapping gap prevents offering a query build as a remedy. Supported data with no suitable registered operation can enter the existing governed coding/admission flow; an empty successful result, unavailable backend or denied activation cannot. Keep any unresolved answer visible after those checks. This is repository retrieval; ADR-064 is planning policy only, with no new persona/planning workflow installed by this change.

### Step 10 - Inspect the evidence behind proof or diagnosis claims

For “which tests cover this AC?”, request `covered_by` at source disclosure level and inspect the returned canonical references. They establish declared tests, not a successful run. Ask separately for an attributable execution receipt when run proof is required; without it, preserve “not established.” The optional request `assessment` and standalone `knowledge assess` surface can inspect supplied proof/readiness/implementation/regression or quoted-clause comparison packets, but supplied evidence is not independently executed or verified by that command. For kernel research, pass the packet in the research request; its repository and source revision must match the research scope. The packet survives clarification and restart without trimming quoted content. Read the final inline `output.payload.assessments[need_id]`, alongside coverage and limitations; a partial research run can expose a validated evidence bundle while retaining its partial status. The retrieval child also records `knowledge_assessment`. An answerability vote does not turn these conditional reports into verified proof, and a report removed by the response budget stays explicitly unresolved.

In kernel capability diagnostics, parse `knowledge_answer` and `knowledge_diagnosis` as JSON. Compare expected and observed repository, source revision, operation and request identity from the matching attempt. A scope violation can establish a violated contract; a missing field alone does not establish a backend root cause. Follow the bounded `next_step.reason` and obtain missing diagnostics before proposing a rerun. Working-tree revision, published source revision and historically tested revision must not be substituted for one another.

### Step 11 - Enable optional observation through the application entry point

Use an explicitly configured existing kernel observability owner:

```sh
python -m integrations.knowledge_cli --observability-config KERNEL_CONFIG retrieve --backend neo4j --repository-id leafcutter --root REPOSITORY --request count-request.json
```

Omit `--observability-config` to remain disabled. Configuration does not grant provider or data-transfer permission. The wrapper uses the existing tracer and redaction policy; it does not add a second telemetry store.

Inspect `observation.state`: `disabled` means no attempt; `unavailable` means initialization or delivery failed; `unverified` means local emission did not establish matching remote ingestion. Follow `trace_url` only when the state is `verified` for the same request/retrieval IDs. The default application composition does not install a remote-read verifier, so local success alone cannot produce that claim. A trace ID or plausible URL is not evidence of remote visibility. Sanitized final shutdown warnings preserve the result and do not rerun retrieval or query construction.

## Verification

Run the count command after substituting your authorized repository and published revision:

```sh
python -m knowledge retrieve --backend neo4j --repository-id leafcutter --root REPOSITORY --request count-request.json
```

Expected shape: a JSON response with execution `status`, `source_sha`, `generation_id`, evidence, `answer` and `observation`. An exact total requires `answer.completeness.complete: true`; a source-field gap must retain missing-field reasons rather than fabricate fulfilled counts. With observation omitted, expect `observation.state: disabled`. See [Troubleshooting](#troubleshooting) for incomplete or unavailable responses.

Verification labels: public kernel/observer acceptance tests exercise the real kernel and application observer with controlled ports/tracers and scripted Jev. They do not prove real Jev decision quality or Langfuse ingestion. Source-oracle counts above are immutable expectations; live Neo4j canary/evaluation receipts must identify the actual tested revision, budgets and storage backend. No live-provider or deployment approval is implied by this walkthrough.

## Troubleshooting

1. **The response is `ok` but work-status counts are absent.** Inspect required-field availability and disclosure. Do not reinterpret lifecycle status; publish the approved mapping when needed, then repeat only the authorized scoped request.
2. **A count is partial or has no exact total.** Inspect truncation, continuation and budget limitations. Refine the population or use an authorized sufficient budget; do not equate the first or final continued page with all requirements. The absence of another cursor is not proof of a complete aggregate.
3. **A query build is unavailable.** Check the pinned mapping and required fields before the query catalog. Missing source data needs an approved mapping/source change, not a new query; backend outages need recovery.
4. **A declared test has no run proof.** Keep the declaration and the missing execution receipt distinct. Do not use a historical result at another SHA as current proof.
5. **There is no accessible trace.** Preserve the answer and explicit observation state. Check the configured owner/permissions and matching diagnostics; do not repeat the query merely to obtain a trace.

## See Also

- [Native graph and saved queries](../reference/neo4j-native-queries.md)
- [Repository answer contracts and proof meanings](../reference/knowledge-retrieval-answers.md)
- [Knowledge retrieval component](../architecture/components/knowledge-retrieval.md)
- [Kernel research and reusable queries](kernel-query-growth.md)
- [Repository query catalog](../analysis/2026-10-01-repository-query-catalog.md)
- [ADR-062](../architecture/adrs/ADR-062-standalone-knowledge-retrieval.md)
- [Documentation index](../INDEX.md)
