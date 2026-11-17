---
title: 'Research with reusable graph queries'
description: 'Configure the kernel query catalog and resume human and coding-agent work in the same research run.'
type: how-to
status: active
created: '2026-10-01'
last_updated: '2026-10-10'
components:
- knowledge_management
- decision_kernel
---
# Research with reusable graph queries

The kernel can ask what you mean, select an existing graph query, or hand a missing query to a coding agent. The agent returns a bounded recipe and expected-result tests. Trusted code compiles parameterized Neo4j Cypher, independently executes verification, and admits the query only when the task has `write_query_catalog`. The original research then continues. Ordinary read-only tasks cannot activate queries.

The persistent query catalog is separate from the kernel capability registry. A research run keeps its kernel registry snapshot and immutable graph source revision; a verified query digest may be added explicitly through its activation child. The catalog rechecks persisted integrity on reopening. No graph schema/data writes or embedding-provider calls are needed for this flow.

The catalog accepts the current native compiler format only. Obsolete catalogs
need a separately verified replacement; their old request pins are not runtime
aliases. See the [saved-query contract and completed application cutover](../reference/neo4j-native-queries.md#saved-native-queries).

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

The example leaves the component unspecified so the kernel can ask for missing meaning. For the historical component-query demonstration, the answer was `git_vcs_operations`; other questions may need a different clarification or no clarification. Put a known authorized component in `scope.component_ids` when appropriate. Supply `scope.revision.commit` when a particular immutable published revision is required; inspect the actual source identity returned by retrieval.

## Interpret a question before selecting its query

For a configured and permitted graph source, a research question without explicit
`answer_requirements` first issues `interpret_retrieval_needs` through
`host.retrieval_needs`. This applies with or without a persistent query catalog.
The caller still supplies a question and authorized scope, not a query operation.
An existing explicit answer contract bypasses this additional interpretation;
native-only research keeps its existing route.

The kernel returns the normal pending host packet. Read its input artifact and
`output_requirements`; all five dimensions are interpreted together. The host
returns `leafcutter.retrieval_needs_output.v1` through the existing submission and
resume interface. A generic model endpoint is not called automatically: the host
that handles this packet supplies the LLM response. If host work is disabled or
unavailable, the run retains an explicit unresolved result.

| JSON field | Purpose |
|---|---|
| `original_question`, `source_scope` | Echo the pending request unchanged; neither the response nor context grants access. |
| `selections` | Required entity types, target IDs, fields, document types and relationships, using offered labels only. |
| `uncertain`, `unresolved` | Preserve missing meaning; unsupported meaning includes the exact standalone `needs_outside_catalog` marker. |
| `detail_mode`, `completeness` | Specify fields/document/context detail and single-item/set/count/example coverage. |
| `hierarchy_scope`, `hierarchy_levels` | Preserve root/parent inclusion and explicit L0–L3 filters; an empty levels list means all levels. |
| `scope_resolution`, `status` | Distinguish usable interpretation, required discovery and a missing user choice. `decided` does not prove correctness. |

For an acceptance-behavior question, the host requests canonical `criteria`.
For what tests or verification must demonstrate, the host instructions request
both `criteria` and authored `test_spec`: required behavior and prescribed checks
are complementary evidence. An explicit criteria-only, specification-only,
reference-only or status-only question keeps that narrower meaning; prior context
does not add unrelated fields. Declared tests are not proof that tests ran.
For a count, the accepted level and inclusion choices reach the actual query.
System validates identities and offered labels, preserves the result on child requests as `retrieval_needs`, and projects
compatible `answer_requirements`. Jev then makes bounded selections from the
executable operations. Catalog configuration does not bypass this path.

A missing user choice uses an ordinary human continuation. Resume the same run;
a new clarification may produce another interpretation packet, while the original
question and trusted scope remain fixed. Unsupported populations, missing fields,
stale or unavailable sources and truncated evidence remain limitations. A source
or schema gap does not authorize query construction or publication.

The integrated route is bounded field projection. `full_document` and unsupported
or multiple relationship obligations return an explicit unresolved result. Safe
projected metadata includes field locators; canonical `criteria` is disclosed from
the immutable source. An explicitly requested `test_spec` is read separately at
level 3 from the same pinned file and returned as its own `/test_spec` citation.
It consumes the existing evidence and content budgets; a missing disclosure is
not proof that the authored field is absent. Verified saved entity queries are selectable with their
digest, but new query construction still has the existing component-scoped input
contract. An arbitrary target cannot be changed into a component to force a build.

Counts also retain existing result, content, candidate and depth limits. The
default `top_k: 6` cannot complete a population of fifteen descendants. Inspect
`answer.completeness` and the returned source; partial rows are not an exact total.
The public bundle retains these facts under `assessments[need_id]` with
`kind: retrieval_answer`. A budget that prevents the final answerability judgment
also leaves the result partial.

[The current flow](../product-truth/flows/leafcutter/retrieval-current-baseline.flow.json)
shows System, host LLM and Jev as separate owners with checked inputs and outputs.
The standalone Oct3 experiment shares the host contract but retains its historical
8/12 semantic result. Controlled integration tests establish transport and
query handoffs; the dated local-storage verification below separately establishes
two exact-AC cases with actual Jev decisions. The later
[canonical publication receipt](../../reports/retrieval-aura-2026-10-09/publication-receipt.json)
establishes graph publication at `2a8ebc87ce937a0a2fec65ab26220f79a72e4859`,
with semantic readiness false. The
[closed Aura evaluation](../../reports/retrieval-aura-2026-10-09/runs/published-2a8ebc87/review.html)
matched selected criteria in 3/3 positives but answered the whole question in 0/3:
the fresh interpretations omitted authored test specifications. Terminal statuses
were partial, partial and completed; the stale control passed. That baseline stays
unchanged. The [later interpretation gate](../../reports/retrieval-needs-precision-v2-2026-10-09/stage1b/review.html)
passed 16/16 frozen cases. The authorized [live retest](../../reports/retrieval-aura-2026-10-09/runs/precision-v2-44406d9/review.html)
then retained both fields in 4/4 interpretations and delivered 2/3 correct complete
positive answers, with a passing stale control. One correct interpretation stopped
at query selection: 0.71 probability was below the unchanged 0.80 gate, so no
retrieval ran. The narrow interpretation fix is accepted; query-selection reliability
and the full live positive gate remain open. The retest used runtime `44406d923`,
source `2a8ebc87`, six Jev calls and four accepted host results without retries.
Multi-method search, traversal and automatic strategy learning remain outside
this integration.

The executable needs handoff currently accepts `detail_mode: fields` and one
supported entity/document pair: ac/ac_yaml, adr/adr, ticket/ticket,
component/component, flow/flow, decision/decision or test/code. Multiple pairs,
`bounded_context`, `full_document` and unsupported document kinds are unresolved
before query execution. Returned entity kinds must match. The standalone
interpreter can describe broader needs; that does not make them executable here.

## Bounded relationship examples and source content

The question can request one existing relationship recipe using one original
anchor and `completeness: examples`. The anchor identifies where to start; the
selected entity/document pair describes the returned records.

| `selections.relationships` | Original anchor | Returned pair and registered operation |
|---|---|---|
| `["covered_by"]` | One acceptance criterion | `test/code` through `get_related_tests`. |
| `["governing_adrs"]` | One authorized component | `adr/adr` through `get_relevant_adrs`, using declared `component_membership`. |
| `["component_context"]` | One authorized component | One supported pair through `get_component_context`; actual mixed-kind results remain partial. |

These recipes preserve the original anchor in `answer_requirements.scope.root_id`;
related results do not have to share its identity. Multiple anchors, multiple
relationships, and exhaustive relation sets or counts remain unsupported. A
component outside an explicit trusted component scope is refused. An unrelated
exact lookup cannot satisfy the requested relationship.

`content` requests a bounded canonical-source excerpt at disclosure level 3,
with its exact locator and revision. It does not request or prove a whole document.
See [content availability](../reference/knowledge-retrieval-evidence.md#bounded-content)
for unavailable, empty, withheld and truncated results. Full ADR filename stems
remain intact as literal candidates; a shortened ADR prefix is not invented.

The real component-context operation can return its Component seed alongside
neighbors. The one-result-kind guard retains that mismatch as partial. Controlled
ADR-only port tests prove host/selection transport and lifecycle, not a fulfilled
answer from the real mixed-kind operation or current Aura publication.

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

The [Oct9 blind interpretation receipt](../../reports/retrieval-public-2026-10-09/needs-evaluation/controller-envelope-repair/summary.json)
records sixteen accepted completed interpretations: all twelve unchanged semantic
cases and four independently frozen holdouts passed. The controller initially used
an invalid actor ID; identical response bytes were submitted to the same waits
with a valid encoding, without generating new model responses. Model identity,
underlying request count and tokens remain unknown. This establishes interpretation
results for that frozen set, not end-to-end retrieval or live Jev selection quality.
The historical Oct3 result remains unchanged.

The [Oct9 public report](../../reports/retrieval-public-2026-10-09/index.html)
keeps the original baseline and repaired runs separate. Initially all six runs
were partial: none of the five positive questions completed, while the stale-source
negative control passed. The [source comparison](../../reports/retrieval-public-2026-10-09/baseline-source-comparison.json)
confirms that P01/P02 lost an existing authored `test_spec`; the source was not
missing that field.

The [final guarded-code verification](../../reports/retrieval-public-2026-10-09/final-verification/verified-summary.json)
completed both exact-AC cases, with and without catalog configuration. Returned
`criteria` and parsed `test_spec` matched the actual pinned Git source and retained
separate field citations. The runs reused the original blind needs responses
unchanged and made four fresh TypeSafe Jev calls. This proof used a bounded local
projection with the real Git source resolver, not live Neo4j. The report also
records 56 passing controlled public/disclosure cases; these are a different kind
of evidence from actual-provider results.

Broader count and discovery cases were not rerun as part of that repair. Their
original failures remain open: descendant operation probabilities of .76/.75
were below the unchanged .80 selection threshold, the default six-result budget
cannot exhaust fifteen descendants, and a topic-wide count excluding parents
still has no supported exhaustive population operation. The integration AC
`KM-500e-1-i` remains in progress, as do the wider retrieval quality and publication
work items.


`reports/knowledge-query-growth-aura.json` records the actual Aura run at source `9f70de80ebcafe59ff55cce6732deb92069f9541`: compiled-query verification and activation, same-research evidence, reopened checkpoint and subsequent reuse from the persistent local catalog. The graph was read-only; the only persistent write was the configured local query catalog. Jev and human/host delivery were scripted in this proof. The real-provider combined check was not run because automatic approval review required explicit authorization for sending the repository context to `api.typesafe.ai`.

The older knowledge-query scanner still answers source-artifact lookup requests. It does not automatically enter this kernel clarification/build/admission loop. Agents wanting governed reusable queries should use the kernel run/resume interface above; direct standalone retrieval remains appropriate when the operation and parameters are already known.
