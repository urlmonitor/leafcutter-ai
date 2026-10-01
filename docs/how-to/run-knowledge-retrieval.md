---
title: Run standalone knowledge indexing and retrieval
type: how-to
status: active
created: '2026-10-01'
components:
- knowledge_management
- decision_kernel
last_updated: '2026-10-01'
description: Overview of Run standalone knowledge indexing and retrieval.
---
# Run standalone knowledge indexing and retrieval

Run commands from the trusted Leafcutter checkout. Indexed Git objects are data, never executable parsers. Architecture and source rules: [ADR-062](../architecture/adrs/ADR-062-standalone-knowledge-retrieval.md), [Stage 0](../analysis/2026-10-01-knowledge-retrieval-stage0.md), [component](../architecture/components/knowledge-retrieval.md).

## Optional startup and development database

```sh
python -m knowledge capabilities
python -m pip install -r knowledge/requirements-neo4j.txt 'pydantic>=2,<3'
docker compose -f knowledge/compose.yaml up -d
```

The first command returns disabled without connecting to Neo4j or loading optional SDKs. Kernel defaults likewise preserve ordinary repository retrieval. Before Compose, set LEAFCUTTER_NEO4J_WRITER_PASSWORD through your environment. knowledge/.env.example lists nonsecret placeholders; it is not automatically loaded. Compose binds localhost ports 17474 and 17687 and pins the Neo4j 5.26 Community image digest. Verified development server: 5.26.31, Python driver6.0.3; other versions and Aura are not implied tested.

Serving uses LEAFCUTTER_NEO4J_URI, LEAFCUTTER_NEO4J_USERNAME and LEAFCUTTER_NEO4J_PASSWORD. Publication uses the same URI plus distinct LEAFCUTTER_NEO4J_WRITER_USERNAME and LEAFCUTTER_NEO4J_WRITER_PASSWORD. LEAFCUTTER_NEO4J_DATABASE defaults to neo4j. Use verified TLS remotely. Separate writer/serving privileges where the deployment supports them; the local Community administrator account does not prove read-only user enforcement. Never put secrets in request JSON. No arbitrary Cypher is exposed.

## Immutable validation and publication

```sh
python -m knowledge validate --root REPOSITORY --repository-id leafcutter --revision REVISION
python -m knowledge plan --root REPOSITORY --repository-id leafcutter --revision REVISION
python -m knowledge sync --root REPOSITORY --repository-id leafcutter --revision REVISION
python -m knowledge status --root REPOSITORY --repository-id leafcutter --revision REVISION
```

REPOSITORY is an absolute trusted checkout; REVISION is an exact commit SHA. Validation and plan do not connect or publish. Sync reads immutable Git objects, builds a full generation and atomically publishes after validation. Repeating the same revision/mapping reuses its generation. Failed builds leave the previous generation active; stale or non-descendant publications cannot silently replace it.

Supported initial canonical surfaces are ACs, components, ADRs and referenced path-keyed files/tests. Other surfaces have colliding IDs and are explicitly excluded, never silently deduplicated. Required missing references fail closed. Audited historical source blockers are ACS-200d -> ACS-200b, ACS-600e -> ACS-600b and ACS-600e -> ACS-300f; this work does not modify those historical ACs. No full-corpus success is claimed until those references are repaired through the normal AC process.

For an isolated supported-surface demonstration:

```sh
python -m knowledge sync --root REPOSITORY --repository-id leafcutter-docs-demo --revision REVISION --surfaces adrs components
```

Projection scope is fingerprinted; changing surfaces under an existing published identity is rejected. The separate demo identity cannot overwrite the full repository projection. Production Decision/Lesson/Policy mappings are unsupported. Reviewed synthetic records demonstrate history mechanics only; runtime traces/run roots do not become canonical history.

## Typed retrieval and disclosure

Save this request as request.json, substituting the published repository and canonical ID:

```json
{"request_id":"manual-1","repository_id":"leafcutter","operation":"get_entities","mode":"exact","arguments":{"entity_ids":["KM-KGS-100a-3"]},"revision":"latest","disclosure_level":0,"budget":{"max_results":2,"max_content_bytes":8192,"max_estimated_tokens":2048}}
```

```sh
python -m knowledge retrieve --backend neo4j --repository-id leafcutter --root REPOSITORY --request request.json
```

Level0 discovers identity/title/provenance, level1 adds bounded relationships, level2 approved summaries/correction context, level3 a bounded excerpt read from the pinned SHA. Repeat with selected IDs and the returned source SHA. Source quotations preserve whitespace; summaries and derived graph context are labeled. Missing source returns explicit limitations. Read roots/deny rules apply at the kernel boundary.

Other registered graph operations include component context, acceptance criteria, related tests, relevant ADRs, policies and reviewed decision/correction/lesson/evidence relationships where mapped. Unsupported mappings return unsupported, never fabricated applicability. Exact absent IDs return ok with empty evidence; outages are unavailable, missing generations stale, invalid inputs structured errors. Inspect requested/executed mode, source SHA, generation, retrieval ID, warnings, truncated and continuation.

Resume a continuation with exactly the same repository, operation, arguments, revision, disclosure and budget, adding the returned continuation string. It stays pinned to the retained generation and consumes cumulative rounds/bytes/tokens/candidates/deadline. Changed inputs, tampering and expiration are rejected. Do not automatically exhaust every cursor. Cancel, unavailable sources, unchanged evidence, adequate disclosure and exhausted budgets stop focused follow-ups.

## Kernel integration

Set knowledge.backend=neo4j, trusted knowledge.repository_id and absolute knowledge.repository_root in kernel configuration. Add a source kind graph_query with its evidence categories; overrides replace source lists, so preserve other desired sources. A leafcutter.retrieval_request.v1 payload can include the optional knowledge operation/mode/arguments/disclosure object. Invocation and repository identity are bound by the composition root; backend sessions, queries and writer credentials do not enter kernel state.

The existing retrieve.repository binding consumes canonical Evidence/SourceVersion. Obvious exact and relationship choices avoid Jev; ambiguous supported semantic choices use the existing reserve-before-use Jev framework. Compact discovery precedes selected-ID source disclosure. The existing research sufficiency judgment decides whether evidence answers the question. Similarity scores are ranking signals, never correctness probabilities.

Evidence IDs are stable for locator/content; retrieval IDs identify separate runs. Capability diagnostics and existing tracer record modes, SHA, generation and retrieval references. Graph provenance is explicitly derived context, source excerpts stay unchanged. Telemetry outages preserve retrieval with a warning. Async hosts await environment.aclose() before closing their loop; synchronous hosts call environment.shutdown() afterward. A synchronous shutdown inside a running loop is explicitly rejected.

## Embeddings and honest evaluation

Graph readiness is separate from vector readiness. Enable embeddings_enabled and set embedding_model, embedding_dimensions and endpoint/token environment-name settings. LEAFCUTTER_EMBEDDING_ENDPOINT is an explicitly configured HTTP gateway accepting POST JSON {model,texts} and returning {model,vectors}; it is not the OpenAI API protocol. Remote HTTPS is required; loopback HTTP is allowed for fixtures. No provider calls run unless enabled.

The ingestion API is knowledge.embedding_jobs.embed_snapshot(writer,snapshot,provider,cache={}); callers own persistent cache storage. Retrieval does not silently ingest. Changed text/model is ineligible until matching vectors exist. Standalone retrieve/evaluate accept --embeddings --embedding-model NAME --embedding-dimensions N. Missing or incompatible vectors return explicit readiness errors while graph retrieval remains available; no silent fallback is performed.

```sh
python -m knowledge evaluate --backend neo4j --repository-id leafcutter --root REPOSITORY --cases cases.json
```

Reviewed case fields are id, reviewed_by, synthetic, request, relevant_ids and correction_ids. Reports record revision/backend/model/query versions, precision/recall at k, correction coverage, provenance validity, bytes and latency. Deterministic vectors prove mechanics only and report semantic_usefulness_proven=false. Real-model evaluation is not run in this implementation session; a representative reviewed baseline and quality thresholds require that distinct evaluation.

## Merge synchronization and recovery

.github/workflows/knowledge-sync.yml activates only when KNOWLEDGE_SYNC_ENABLED=true and writer secrets are set. It handles canonical main pushes or explicit main-branch exact-SHA replay, verifies ancestry, serializes jobs and invokes standalone CLI. It is inactive on this feature branch until a later merge; no workflow run, push or merge was performed here. PR previews cannot publish canonical state.

```sh
python -m knowledge rollback --root REPOSITORY --repository-id leafcutter --generation-id RETAINED_GENERATION
python -m knowledge cleanup --root REPOSITORY --repository-id leafcutter --generation-id EXPIRED_GENERATION
```

Rollback selects a retained generation. Cleanup affects only the selected expired, non-active, projector-owned generation; foreign data is protected. Rebuild an empty authorized database from the same immutable revision/mapping and compare identities, edges/provenance; repeat sync for idempotence. Rebuild vectors with the same model and retained outputs where exact reproducibility matters.

Restore connectivity then replay a failed revision. Repair canonical reference errors in source before replay. Continue explicit graph requests during vector outage; never interpret unavailable semantic retrieval as no match. Inspect published SHA/status for lag and telemetry-loss diagnostics when trace export fails. Actual external merge execution, production memory mapping and real-model usefulness remain separately identified verification limits.

### Aura environment compatibility

Serving accepts `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` as aliases for the default `LEAFCUTTER_NEO4J_*` names. Aura hosts ending in `.databases.neo4j.io` default to username `neo4j` when none is provided. `NEO4J_INSTANCE` is metadata, never a database name; database selection uses an explicit nonempty `database` setting first, otherwise `LEAFCUTTER_NEO4J_DATABASE` or `NEO4J_DATABASE` through the same source precedence, then `neo4j` as a fallback. The unset configuration default is `null`, so a saved Aura database is honored. Existing explicit database strings, including `neo4j`, continue to override environment values. Writer commands accept both database environment names.

Enabled serving and writer composition resolve each setting from the process environment, then the file named by `LEAFCUTTER_ENV_FILE`, then the nearest `.env` walking upward from the configured repository root (or current directory). Within a source, the legacy `LEAFCUTTER_*` name wins over its alias. Empty values count as absent, matching kernel credential loading. Custom configured variable names are exact: they do not fall back to conventional aliases. Named unreadable files fail; unreadable discovered files emit a generic warning. Loading never mutates the process environment and disabled serving never reads credential files.

Keep the actual `.env` outside Git and set `LEAFCUTTER_ENV_FILE` to its existing path when a worktree cannot discover it. Do not copy credentials into the worktree. Writer operations accept the shared URI but still require `LEAFCUTTER_NEO4J_WRITER_USERNAME` and `LEAFCUTTER_NEO4J_WRITER_PASSWORD`; serving credentials do not silently authorize writes. Merely configuring Aura does not run migrations or index a corpus.
