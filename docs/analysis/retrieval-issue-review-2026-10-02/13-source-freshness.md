---
title: 13 - Published source freshness (S9 / RS-21)
description: Historical analysis and saved observations for 13 - Published source
  freshness (S9 / RS-21).
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# 13 - Published source freshness (S9 / RS-21)

Analysis and options only, 2026-10-02. No publication, provider call, secret change, runtime change or AC edit was performed. Source inspected at code commit `887c66d3896ba7727ce41b743887210a3883c6ce`.

## Finding and current evidence

The publication mechanisms exist; automatic operation and a complete reader-facing freshness contract remain unproven. An agent cannot infer current data from a successful merge, available credentials, a healthy database, or an answerability vote.

The retained fresh-retest receipt `reports/retrieval-scenarios-2026-10-02-retest-887c66d3/readiness.json` observed at `2026-10-02T17:51:17.321971+00:00` records repository `leafcutter`, source `59269e024e4d0290b68b03d0d382745966e67e29`, mapper `7`, generation `20c370b99a39e0939e985846c9132986f8dc3052007b0dec5b43c19ddda7c28f`, 9,047 nodes, 23,612 edges and `semantic_ready=false`. This is a readback observation, not a merge-trigger receipt. Local Git confirms the inspected code descends from that source, with 107 additional commits; this does not establish that every changed file requires graph remapping.

`config/kernel_config.default.json:3,125` contains **15 sources**, `knowledge.backend=none`, and no `graph_query` source. `knowledge/config.py:58` returns the disabled retriever before loading credentials. The default-source retest used immutable native bytes at `887c66d3`, reached `waiting_host / synthesize_evidence`, and demonstrated no final answer (`reports/retrieval-scenarios-2026-10-02-retest-887c66d3/default-source/results.md`). The graph-only canary is a separate configuration. A local `.env` therefore proves neither graph selection nor CI writer enablement. The parent investigation reports repository-secret metadata count zero and no canonical-trigger publication receipt; this analysis did not repeat that remote inspection, and repository metadata alone would not exclude inherited organization/environment configuration.

`templates/agents/research-agent.md:171` requires curated source findings; IT PO boundaries at `templates/agents/it-po.md:110` separate requirement enrichment from source implementation. This review supplies evidence and proposals, not their phase sign-offs. `CLAUDE.md` requires behavioral gate proof; `templates/agents/test-writer.md:588,884` requires authoritative ACs and an actual RED baseline before implementation.

## Existing contracts and precise gaps

| Anchor | What exists; remaining limit |
|---|---|
| `.github/workflows/knowledge-sync.yml:3,16,31,41,54` | Main push or main-branch manual dispatch; enable variable; separate writer settings; exact-SHA/ancestry check; serialized validate/sync/status. No schedule, pre-merge validation job, or durable publication-receipt artifact is declared here. Workflow presence proves no execution. |
| `knowledge/cli_sync.py:75,154` | Immutable source loading; unchanged projection scope; descendant check; compare-and-swap publication; requested versus published SHA status. Status currently uses writer configuration. `knowledge/__main__.py:142` correctly returns failure for stale results. |
| `knowledge/projection/canonical_loader.py:53,79,134` | Mapper 7; pinned Git input; generation hash includes repository, source SHA, mapper and selected surfaces. Source identity differs from running writer/query code identity. |
| `knowledge/adapters/neo4j_projection.py:28,110,130,206` | Validated staging, count checks, immutable digest collision refusal, atomic active-pointer switch and retirement-based scoped cleanup. `neo4j_backend.py:170,188,363` supports retained generations/exact revisions and defaults retention to 3,600 seconds. |
| `knowledge/retrieval_steps.py:29` | `latest` selects active published data. Exact SHA can select retained data; otherwise reports stale and withholds evidence unless `allow_stale`. No comparison to workspace/main is implied by `latest`. |
| `knowledge/semantic.py:51` | Semantic readiness requires provider, ready vectors and matching model/dimensions. Graph publication cannot establish semantic usefulness or embedding completion. |

All ACs below are `status: active`, `readiness: approved`. In `docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/`, `KM-400b-1` through `KM-400b-5` are `work_status: done`: immutable preview, invalid-source rejection, atomic/non-regressing publication, change/delete/rename handling, rebuild/rollback/cleanup. `KM-400d-5` and `KM-400e-5` are also done: attributable freshness and observable standalone synchronization. Preserve their bounded evidence.

`docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500d-2.yaml:11` is **in_progress**, with empty `covered_by` and `implemented_by`; it explicitly requires branch/trigger/lag distinctions, actual canonical-event proof, separate embeddings, overlapping-generation capacity, actual serving privileges and durable job correlation. These are outstanding acceptance obligations. `KM-500g-2` is also in_progress and governs matching-attempt diagnosis; RS-21 additionally lacks the accepted wording handoff. Existing `tests/knowledge/test_workflow.py:13` parses workflow strings; despite its reachability tag, it does not execute event gating or publication. No new execution coverage is claimed here.

## Reader contract: how agents detect unsuitable data

Require an explicit freshness policy: **latest published**, **exact historical SHA**, or **current requested ref resolved once to SHA**. Preserve the policy and resolved target through waits/restarts. Resolve a moving branch through the trusted source owner, record when it was observed, and do not reinterpret it mid-run. Local edits require a separately identified content snapshot; a Git SHA cannot label dirty bytes. The native-path issue also appears in `kernel/capabilities/retrieval/versioning.py` and the S9 completion-gap analysis.

Expose repository, source kind, requested/published/actually-read SHA, generation, mapper, scope, observation time, graph/vector readiness, and synchronization state: disabled, unknown, pending, failed or confirmed. A publication receipt additionally records actual trigger, workflow/job or manual invocation identity, writer code SHA, mapping/schema identity, validation outcome, expected/activated generation and readback. Query execution and historical test receipts retain their own code/source identities. Missing receipts mean **trigger not established**, not publication failure.

Distinguish four remedies:

1. **Source fact absent:** the canonical source at the requested revision does not contain it. Report the gap; its source owner must author it.
2. **Mapping absent:** the fact exists in source but the generation lacks its field/type/relation. Require approved mapping and republishing. `knowledge/capability_fit.py:11` distinguishes unsupported mapping/field gaps from missing queries.
3. **Generation stale:** suitable mapping exists, but the requested source is not published. Wait for publication or select an explicitly permitted immutable alternative.
4. **Query absent:** source and mapping support the need, but no usable query exists. Only this case permits query-build routing.

A newer SHA is not proof of factual correctness: validate source contracts, content hashes and declared relationships; compare relevant citations to the pinned source. Unknown diagnosis stays unknown. Jev may select an offered permitted alternative or judge evidence sufficiency; deterministic source checks own freshness. Jev cannot declare an older generation current, erase a missing-trigger limitation, or authorize ingestion.

## Options and recommended minimum

| Option | Tradeoff |
|---|---|
| A. Manual exact-SHA publication plus explicit reader pins | Small operational surface; acceptable for occasional snapshots. Updates depend on an operator, with no automatic freshness promise. |
| B. Automatic canonical-main publication plus manual replay and visible freshness | Recommended. Reuses current workflow and writer; adds deployment proof, durable receipts and a reader contract. Some lag after merge remains explicit. |
| C. Scheduled reconciliation in addition to B | Recovers missed events automatically, but adds credentials use, capacity/cost and concurrency decisions. Adopt after B is proven, only if the agreed lag objective needs it. |

For B, use one owner per step:

| Step | Sole owner and observable output |
|---|---|
| Configure | Deployment operator selects repository/database/canonical branch, enablement, writer principal, serving principal, retention and capacity limits. |
| Pre-merge validate | CI validation job checks the candidate immutable source without publishing. Failure prevents claiming publishability. |
| Trigger | Canonical CI workflow enqueues main's immutable event SHA; manual recovery records `manual` and its exact SHA. Feature merges/local edits do not trigger a main promise. |
| Build/publish | Standalone writer validates full snapshot, checks scope/ancestry, stages and atomically switches the pointer. Changed/deleted links/entities disappear only in the new generation; retained historical evidence stays intact. |
| Confirm | Publication job persists sanitized outcome/readback and actual event identity independently of later retrieval telemetry. Pin and record the executing writer code; current checkout of moving `main` otherwise makes replay code distinct from source SHA. |
| Read | Retrieval owner checks requested policy against manifest/source evidence; delivers attributable readiness and limits to agents. No writer credentials enter research. |
| Embed | Embedding-job owner separately schedules changed text/model, records generation/model/dimensions and failure/pending state. |
| Retire/rollback | Maintenance owner preserves cursor lifetime plus margin, protects active/foreign data, enforces total retained/building/vector capacity, and explicitly records rollback to a retained generation. |

Required configuration: `KNOWLEDGE_SYNC_ENABLED=true`, repository/database selection and CI URI/writer secrets; independently enable reader `knowledge.backend=neo4j`, trusted root/repository and authorized `graph_query` source while preserving desired native sources. Verify actual database privileges; different environment-variable names do not establish distinct permissions. Embeddings need separately approved provider/model/dimensions and matching indexes. These are prerequisites, not changes authorized by this review.

## Proof before completion

Test-writer first captures RED on the public status/reader/workflow boundary for the missing contract, using real-format source fixtures and meaningful assertions; no grep-only gate proof. Then preserve existing mechanism tests and add:

- **Positive:** authorized canonical event publishes B once, exact readback/citation matches B, repeat replay is idempotent; separate manual run is visibly manual. Latest-published and exact-historical policies both retain honest labels.
- **Negative:** dirty edit, feature merge, disabled backend, missing credentials, unknown trigger, foreign scope and unpublished requested SHA never become current/fresh. A permitted older alternative retains stale status. Graph-ready/vector-unready remains usable only for compatible graph operations.
- **Failed publication:** malformed source, duplicate IDs, required missing endpoint, interrupted batch, count mismatch, losing CAS and out-of-order/non-descendant events leave complete A active and record failure; resume reuses the exact staged snapshot.
- **Change/deletion:** B renames an ID-bearing AC, changes content and deletes a node/link; B exposes new content with canonical ID preserved, while pinned A retains old evidence. Path-identified source files retain path-identity semantics.
- **Rollback/retention:** explicit B-to-A rollback is observable; active/foreign/unexpired cleanup is refused; expiration is explicit and never silently switches cursors. Exercise capacity with overlapping generations and vectors.
- **RS-21 wording:** evidence without an event receipt can state observed SHA/readiness, cannot assert a merge job ran; rejected/stale wording replies cannot trigger another retrieval or lose the limitation.

Dependencies are existing publication/retention contracts, source-selection policy, the common attempt/evidence contract and wording acceptance. Authorized real CI/manual publication, database privilege tests, capacity measurements and embedding/deployed proof remain **not run here**. A manual success cannot close the canonical-event clause of KM-500d-2.
