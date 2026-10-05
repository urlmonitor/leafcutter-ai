---
title: 'ADR-062: Standalone Knowledge Retrieval over Immutable Git Projections'
description: 'The user-authorized knowledge retrieval boundary, immutable Neo4j generations, existing canonical identities and thin kernel integration.'
type: adr
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components:
  - knowledge_management
  - decision_kernel
related_docs:
  - docs/architecture/components/decision-kernel.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/analysis/2026-10-01-knowledge-retrieval-stage0.md
---
# ADR-062: Standalone Knowledge Retrieval over Immutable Git Projections

## Decision status

Accepted for the user-authorized standalone knowledge retrieval implementation on 2026-10-01.

## Context

The 2026-10-01 user-supplied Knowledge Retrieval Implementation Guide requests a complete standalone retrieval subsystem and a thin adapter to the active kernel v0.1. The earlier colony-memory delta is a draft: its kernel/memory location, mutable incremental ingestion, direct learned-node writes and deferred vector work are proposals, not the selected implementation boundary for this request. Existing accepted ADRs retain their authority; in particular ADR-056 does not make usage a correctness signal, ADR-034 owns learning writes, and ADR-040 governs their publication.

## Decision

Knowledge Retrieval is a separately importable and executable top-level package. It owns projection, registered queries, Neo4j and optional embedding adapters. It does not import kernel state, LangGraph, checkpoints or internal decision types. The application composition root injects its port into the existing capability mechanism; the adapter converts serializable evidence into the kernel's existing Evidence and SourceVersion contracts. Kernel-owned lifecycle, identity, permission, budget and observability facilities remain authoritative.

Git is canonical. Ingestion reads one immutable commit through existing loaders and validates identities and references before publication. The existing graph producer and source declarations remain authoritative for declared graph semantics. Projection keys include repository, generation and canonical identity. Projection-only fields never replace canonical IDs. Ambiguous relationships retain their declaration and provenance rather than being silently promoted to proof.

Each full snapshot becomes an immutable generation. Publish one validated generation atomically with non-regression protection. Queries pin one generation; deletions disappear in the next publication. Failed builds leave the active generation untouched. Cleanup is restricted to projector-owned generations after continuation retention expires. Ingestion and retrieval have separate execution and credential lifecycles.

Registered, bounded, parameterized operations are the only query execution surface. Arbitrary model-generated Cypher is excluded. Graph readiness and semantic readiness are distinct. Optional embeddings use model, dimension, text hash and generation eligibility. The complete MVP demonstrates semantic candidates and bounded graph expansion; synthetic demonstrations remain labeled until an approved historical corpus exists.

No new runtime Decision/Lesson persistence store is introduced here. Reviewed Git artifacts may be projected using an explicitly documented extension that preserves existing Decision identity. Raw Langfuse observations and direct Neo4j writes do not become canonical memory. The run root and existing gap stores retain their authority.

Backend-off operation requires no Neo4j, embedding or telemetry SDK. Disabled, unavailable, unsupported and stale are distinct from an empty successful search. Progressive disclosure preserves identity, source SHA and locators through bounded exact-source excerpts.

## Consequences

The Stage 0 source audit must close the mapping and adapter compatibility gate before production mappings ship. A graph-only implementation is a milestone, not completion of the requested hybrid MVP. A real supported Neo4j test run is required to claim server compatibility; offline fixtures cannot establish it. Backend versions, test environment and any unverified release gates must be recorded.

This decision replaces the conflicting proposals in the draft colony-memory delta for this retrieval feature only. It does not redesign the kernel, authorize autonomous learning publication, or supersede the long-term reinforcement rules of ADR-056.

## Initial declared scope

The independent projection audit measured 97 colliding raw IDs across the legacy producer's surfaces (for example, agent entries and documentation stems). Therefore the initial production projection explicitly selects the canonical acs, components and adrs surfaces plus their declared file/test targets. It reports excluded surfaces in diagnostics and capabilities. It does not silently deduplicate, rename canonical IDs or pretend every legacy surface is supported. Duplicate IDs inside the selected scope remain publication errors. Synthetic memory is a separate, visibly labeled fixture extension. Wider surface support requires an approved identity mapping first.

## References

- [Knowledge retrieval answer reference](../../reference/knowledge-retrieval-answers.md) - Implemented neutral answer contracts and explicit source limits.
