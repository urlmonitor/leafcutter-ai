---
title: 'Research with reusable graph queries'
description: 'Configure the kernel query catalog and resume human and coding-agent work in the same research run.'
type: how-to
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components:
- knowledge_management
- decision_kernel
---
# Research with reusable graph queries

The kernel can ask what you mean, select an existing graph query, or hand a missing query to a coding agent. The agent returns a bounded recipe and expected-result tests. Trusted code compiles parameterized Neo4j Cypher, independently executes verification, and admits the query only when the task has `write_query_catalog`. The original research then continues. Ordinary read-only tasks cannot activate queries.

The persistent query catalog is separate from the kernel capability registry. A research run keeps its kernel registry snapshot and immutable graph source revision; a verified query digest may be added explicitly through its activation child. The catalog rechecks persisted integrity on reopening. No graph schema/data writes or embedding-provider calls are needed for this flow.

## Configure and start

Use the repository virtual environment. Serving Neo4j credentials and the configured Jev credential are read through the existing external environment-file loader. A real Jev run sends the research question, scoped component identifiers, query metadata and later evidence assessment context to the configured provider. Follow the deployment's authorization before running it.

From the repository checkout, this PowerShell example replaces the two deliberate path placeholders and creates runnable configuration and task files outside Git:

```powershell
$repo = (Get-Location).Path
$catalog = Join-Path $env:LOCALAPPDATA 'Leafcutter/query-catalog-km500'
$configPath = Join-Path $env:TEMP 'leafcutter-query-growth.config.json'
$taskPath = Join-Path $env:TEMP 'leafcutter-query-growth.task.json'
$config = Get-Content knowledge/examples/kernel-query-growth.config.json -Raw | ConvertFrom-Json
$config.knowledge.repository_root = $repo
$config.knowledge.query_catalog_root = $catalog
$config | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $configPath -Encoding utf8
$task = Get-Content knowledge/examples/kernel-query-growth.task.json -Raw | ConvertFrom-Json
$task.scope.repository_root = $repo
$task | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $taskPath -Encoding utf8
python -m kernel run --config $configPath --input-file $taskPath
```

The example intentionally leaves the component unspecified so the kernel can ask a focused question. For the reviewed demonstration, answer `git_vcs_operations`. To reuse a query without this scope clarification, put that ID in `scope.component_ids`. The source revision is resolved and pinned before any pause; add an explicit `scope.revision.commit` when a particular published revision is required.

## Resume the issued interaction

Keep the returned run ID and pending interaction. Build a submission using its exact `id`, `state_revision` and `output_schema_id`; do not reuse stale values. For a human question, the response is `{"free_text":"git_vcs_operations"}`, the actor is `{"id":"user","kind":"human"}`, and the response schema is `leafcutter.human_answer.v1`.

A complete submission has `run_id`, `interaction_id`, `expected_state_revision`, `actor`, `response_schema_id` and `response`. Save it as JSON and resume with:

```powershell
python -m kernel resume --config $configPath --run-id $runId --input-file $submissionPath
```

For `build_query`, the coding agent reads the bounded input artifact and available-query metadata in the packet. It returns `{"candidate": <authored candidate>}` with host actor and the packet's `leafcutter.query_candidate.v1` output schema. `knowledge/examples/component_tests_candidate.json` is the reviewed two-hop example: Component → AcceptanceCriterion → Test. It includes positive and negative expectations at the source SHA recorded in its reviewer attribution. Recheck those judgments before using the example against a changed corpus.

The host cannot declare activation, choose another repository, submit executable Cypher, or grant itself permissions. The native `knowledge.activate_query` capability verifies the candidate and emits a digest-bound receipt. A failed test, altered candidate, unsupported source kind, unavailable backend, denied permission or exhausted budget stays an explicit limitation. It does not silently become an empty answer or another construction attempt.

Queries outside the bounded recipe language need a normal code-build change; this path never executes arbitrary submitted Python or Cypher. Compiled queries support useful paths of up to two directed relationships, allowlisted kinds and parameterized filters. Results remain explicitly partial when fanout limits prevent a completeness claim.

## What was exercised

`reports/knowledge-query-growth-aura.json` records the actual Aura run at source `9f70de80ebcafe59ff55cce6732deb92069f9541`: compiled-query verification and activation, same-research evidence, reopened checkpoint and subsequent reuse from the persistent local catalog. The graph was read-only; the only persistent write was the configured local query catalog. Jev and human/host delivery were scripted in this proof. The real-provider combined check was not run because automatic approval review required explicit authorization for sending the repository context to `api.typesafe.ai`.

The older knowledge-query scanner still answers source-artifact lookup requests. It does not automatically enter this kernel clarification/build/admission loop. Agents wanting governed reusable queries should use the kernel run/resume interface above; direct standalone retrieval remains appropriate when the operation and parameters are already known.
