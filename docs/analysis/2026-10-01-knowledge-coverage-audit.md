---
title: Knowledge retrieval product coverage audit
description: Product requirements mapped to existing acceptance criteria and explicit pending operational proof.
type: explanation
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components: [knowledge_management, decision_kernel]
---
# Knowledge retrieval coverage audit

This audit follows the user's request for PO, BA and IT PO to cover the agreed knowledge indexing, retrieval and research-growth flow with acceptance criteria. The implementation baseline is commit `9d11594782abfb417d0f3a826bfb1f91f3a523ac`. The source is the user-supplied Knowledge Retrieval Implementation Guide dated 2026-10-01 and the subsequently approved Jev clarification, query selection, coding-agent gap resolution, verification, registration and research-resumption flow.

PO owns benefit framing and scope; BA owns observable behavior; IT PO owns technical constraints and test contracts. Existing ACs are reused, not cloned. New criteria are pending work, not evidence that a feature exists. This audit changes no implementation, deploys nothing, and authorizes no provider request.

## Requirement coverage

| Agreed requirement | Authoritative ACs | Coverage and remaining evidence |
|---|---|---|
| Stage 0 inventory, canonical models, IDs and relation direction | KM-400a-1; KM-KGS-100; KM-ADM-100 | Existing alignment and mappings; no competing domain model. Unsupported source types remain explicit. |
| Standalone package, typed contracts, disabled backend and dependency isolation | KM-400a-4; KM-400e-1, e-3 | Implemented bounded contracts and optionality. Kernel consumes the established capability port. |
| Immutable source, safe validation and projection preview | KM-400b-1, b-2 | Implemented; dirty worktrees cannot silently redefine selected source. |
| Idempotent build, atomic publish, stale/concurrent event protection | KM-400b-1, b-3 | Real-server proof exists; a published generation is complete and attributable. |
| Edit, delete, rename and removed-edge reconciliation | KM-400b-4 | Implemented full-generation semantics; no claim of incremental in-place indexing. |
| Rebuild, rollback, retention and owned cleanup | KM-400b-5; KM-400d-3 | Implemented projection lifecycle. Query-catalog lifecycle is separately pending KM-500b-5. |
| Exact, component, AC, test and governing-document operations | KM-400a-2, a-3 | Existing registered operations preserve declared semantics; missing Policy mapping is unsupported. |
| Typed arguments, unknown operation rejection, scope isolation | KM-400a-4, a-5; KM-500a-2 | Implemented. Plain question text cannot become executable Cypher. |
| Reviewed decision/lesson provenance, correction and evidence links | KM-400c-1, c-3 | Approved/synthetic mechanics demonstrated. No new production memory source is implied. |
| Optional semantic candidates, compatible vectors and bounded hybrid expansion | KM-400c-2, c-3, c-4 | Real database plus deterministic-vector mechanics demonstrated. Current Aura publication reports semantic_ready false. |
| Long approved material, attributed chunks, cache versions and entity collapse | KM-500d-4; reuses KM-400c-2, c-4, d-2 | Concrete original-guide implementation gap. Current bounded text rejection is not deterministic chunking. New criterion remains todo. |
| Progressive disclosure and exact-source excerpts | KM-400d-1, d-2 | Implemented four levels; excerpts come from the selected immutable source. |
| Stable evidence, freshness and explicit older-revision permission | KM-400d-5 | Implemented. Retrieval-run identity stays separate from evidence identity. |
| Continuation integrity, cumulative caps, deadlines and cancellation | KM-400d-3, d-4; KM-500c-3 | Implemented bounded control flow; partial results are not complete answers. |
| Jev retrieve/skip/mode selection, deterministic known requests | KM-400e-2, e-3; KM-500a-1, a-2 | Implemented orchestration. Real-provider judgment quality remains pending KM-500a-4. |
| Disabled, empty, unavailable, stale, unsupported and partial distinctions | KM-400e-1, e-4; KM-500a-3 | Implemented, with live empty versus saturated-result proof. Outage/denial never creates a query gap. |
| Merge-driven update, replay, source lag and separate graph/semantic readiness | KM-400e-5; KM-400b-1, b-3 | Workflow/mechanism proof exists. Configured deployment and branch behavior require KM-500d-2. A feature worktree commit is not a merge into the canonical branch. |
| Trace correlation, redaction and tracing-independent retrieval | KM-400e-5; KM-400e-4 | Reuse existing observability owner. Configured operational evidence is part of KM-500d-2; no default trace ingestion. |
| Configuration, setup, backend compatibility, credentials and recovery | KM-400e-1, e-5; KM-500d-2 | Existing runbooks and actual Aura graph deployment are evidence, not universal privilege/capacity readiness. |
| Clarify required inputs and resume the original need | KM-500a-1; KM-500c-1 | Implemented checkpoint/interaction behavior. Scope cannot be broadened by the answer. |
| Select by query purpose, inputs and supported questions | KM-500a-2 | Implemented bounded catalog selection; actual provider validation pending a-4. |
| Proven missing query becomes a bounded canonical build child | KM-500a-3; KM-500b-1 | Implemented gap and host request controls. Actual coding-agent authorship/delivery pending b-4. |
| New useful query compiled, tested and evaluated before activation | KM-500b-2 | Actual novel two-hop query proved. Declared candidate cases are not independent proof of general usefulness. |
| Permissioned, atomic and persistent catalog admission; later reuse | KM-500b-3 | Implemented version/digest/integrity boundary. Current retained query survives process restart. |
| Resume pinned original research, then assess actual evidence | KM-500c-1, c-2 | Implemented with real kernel and Aura; build success is separate from answer sufficiency. |
| Failure, duplicate delivery, no progress and bounded retries | KM-500b-1; KM-500c-3 | Implemented controls and inherited scheduler proof; budgets never reset to hide failure. |
| Agent-facing access and correct frontdoor selection | KM-500d-1 | Pending explicit acceptance over existing scanner, standalone typed CLI and kernel research. No new transport required. |
| Honest metrics and representative usefulness baseline | KM-400c-5; KM-500a-4; KM-500d-3 | Mechanics/reporting implemented. Representative current-source judgments, held-out comparisons and real-provider quality evidence remain pending. |
| Controlled improvement as source and query contracts evolve | KM-500b-5; KM-500d-3 | Pending compatibility decisions, revalidation, retirement/rollback and measured candidate comparison. No autonomous model training or canonical rewriting. |

## Status and evidence boundaries

Coverage now reuses 34 existing behavioral leaves (25 in KM-400 and nine in KM-500) and adds seven pending leaves. The two families contain 41 behavioral leaves and 11 product/benefit parents. These counts describe AC coverage, not passing-test percentages.

KM-400's completed child criteria describe the bounded implementation and expressly distinguish synthetic proof from real-model usefulness. Its obsolete note saying all work was still todo has been corrected. Its done status does not claim that a production historical-memory corpus exists or that an embedding/provider rollout is complete. The original guide is not fully implemented: section 8 states, "Long material uses deterministic chunks carrying parent entity ID, locator, source revision and chunking version." It also requires collapsing chunk hits to entities while retaining locators and version-aware embedding cache identity. KM-500d-4 now records this concrete gap; rejecting large text does not satisfy it.

KM-500a and KM-500b now combine completed behavior with pending verification/lifecycle requirements, so their rollups and KM-500 are in_progress. KM-500c is done for its three existing bounded criteria. New KM-500d remains todo until its operational and evaluation requirements have proof. Previously accepted leaves retain their established criteria and evidence; new leaves start todo with no invented test coverage.

The exact baseline was published to Aura with 6,040 nodes and 19,518 edges. An exact new AC source excerpt and the retained two-hop component-to-test query were checked at that SHA; the latter returned all four independently expected test IDs with status ok and no truncation. This manual publication does not prove that the feature branch is merged, canonical-branch CI is configured, semantic embeddings are ready, or a real Jev/coding provider authored the query.

Evidence sources: [Stage 0 alignment](2026-10-01-knowledge-retrieval-stage0.md), [retrieval acceptance](2026-10-01-knowledge-retrieval-acceptance.md), [Aura acceptance](2026-10-01-knowledge-retrieval-aura-acceptance.md), [query-growth acceptance](2026-10-01-query-growth-acceptance.md), and [neutral catalog verification](2026-10-01-query-catalog-verification.md). Existing evidence reports intentionally retain the source revision at which their tests ran.

## Unresolved architecture boundary

The original guide says, "Do not invent a Leafcutter graph query language." The later approved flow asks a coding agent to create a useful new Neo4j query. The current implementation instead accepts a constrained declarative relationship/filter recipe and compiles it to scoped parameterized Cypher. This successfully expresses the demonstrated novel two-hop query, but its recipe grammar was an implementation choice, not separate explicit user approval of a new query language.

The distinction between constrained registered-template authoring and an unwanted new query language must be resolved through the existing architecture decision process before claiming full guide compliance or unconstrained coding-agent readiness. KM-500b-4 carries that verification boundary; KM-500b-2 remains accepted only for its expressly bounded recipe behavior. This audit neither decides that arbitrary Cypher is safe nor retroactively approves the language choice.

## Boundaries kept outside this request

A new HTTP/MCP service, arbitrary model-authored Cypher, complete code/call graphs, new production Decision/Lesson schemas, autonomous policy/lesson editing, model-weight training, unrestricted self-modification, full trace ingestion, incremental projection redesign and production HA/multitenancy remain excluded or separate roadmap proposals. Self-improvement here means attributable query/capability proposals with independent checks, explicit authorization and retained versions. Approval to write these ACs is not approval for external model calls, deployment, merging or implementing the newly identified backlog.

## Acceptance validation

IT PO validated all **52 KM-400/KM-500 records** with the canonical `validate_ac_schema.py` validator. The actual commit guardian's per-file `_validate_file` checks also passed all 52, using the full **4,511-record AC index**, including test-contract and derived durable-effect checks. Required AC references and parent `covered_by` backlinks were checked explicitly with no missing links. This was targeted acceptance validation, not a claim that a commit or the complete commit-hook chain ran.

All seven new leaves remain `todo`, with empty `covered_by` and `implemented_by`. Their **16 planned test specifications** target existing test directories and identify public, failure or actual-artifact/deployment proof as appropriate; they are not fabricated existing test coverage. Architecture/reference links resolve to existing files. BA clarified the catalog lifecycle's durable persisted selection so its side-effect declaration matches both its intended behavior and the repository checker. No source implementation, test execution against a provider, deployment, merge or commit occurred during this audit.
