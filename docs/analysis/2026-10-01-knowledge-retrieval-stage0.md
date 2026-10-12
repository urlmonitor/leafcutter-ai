---
title: 'Knowledge Retrieval Stage 0: kernel v0.1 alignment'
description: 'Technical ownership, existing contracts, canonical mapping constraints and release gates for KM-400.'
type: explanation
status: draft
created: '2026-10-01'
last_updated: '2026-10-01'
components:
  - knowledge_management
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-062-standalone-knowledge-retrieval.md
  - docs/architecture/components/decision-kernel.md
  - docs/reference/artifact-knowledge-graph-data-map.md
---
# Knowledge Retrieval Stage 0

Target: the knowledge-retrieval-v01 worktree, based on feature/kernel-v01 at 3299cc3c. Repository: urlmonitor/leafcutter-ai. The Windows parent directory is not the Git source repository. The main checkout contains unrelated modifications and is not this implementation target.

This initial IT PO inventory is architecture/configuration verified. Source-symbol behavior and backend execution remain explicit gates for the implementing engineer, because ADR-009 keeps IT PO out of source and tests. Do not interpret an architecture symbol reference as execution evidence. The active target includes a real kernel; the main checkout's absence of that package is irrelevant to compatibility.

| Area | Verified architecture/configuration references | Decision | Required change |
|---|---|---|---|
| Canonical entities and IDs | docs/components.json; config/paths.json; config/ac_store_schema.json; KM-KGS-100a-3 and KM-KGS-100d-4 | Reuse | Project existing IDs, source paths and relationship declarations; scope projection keys by repository and generation |
| Source loader | knowledge-management.md documents load_surfaces_with_meta, build_knowledge_map and extract_edges | Adapt through wrapper | Run on immutable source material; verify source implementations before production mapping |
| Evidence and requests | kernel design part 2 documents Evidence, EvidenceSource, SourceVersion, EvidenceBundle, Request and CapabilityResult | Reuse at adapter boundary | Knowledge returns neutral serializable evidence; adapter preserves kernel evidence identity/validation and exact source revision |
| Invocation | config/capability_registry.json registers retrieve.repository and leafcutter.retrieval_request.v1; output leafcutter.evidence_bundle.v1 | Extend existing entry point | Inject port at composition root; avoid competing schedulers or legacy-agent registry routing |
| Jev | ADR-053; kernel_config.default.json retrieval and research limits | Reuse decision provider | Deterministic exact selection; bounded semantic mode choice only for ambiguity; preserve confidence semantics |
| Tracing | decision-kernel.md and ADR-056 reference CorrelationIds and Langfuse-owned observations | Adapt | Child retrieval metadata via injected telemetry; no Neo4j or Langfuse ownership in kernel state |
| Synchronization | Git source and canonical main branch; user guide full snapshots | Add | Independent validate/plan/sync/status/retrieve CLI and merge job, non-regressing atomic generation publication |

## Canonical mapping constraints

- AC uses its existing full id. component is a kebab-case AC-store namespace; components contains registry IDs. Preserve both and do not replace underscores mechanically.
- Current map relationship types implemented_by, covered_by, depends_on, component_membership and configured additional fields remain declared relationships. Typed retrieval recipes may interpret them only with endpoint/source-field validation.
- KM-KGS-100d-4 (September 25) takes precedence over stale August architecture prose about phantom-edge exemptions: normalize file targets as repository-relative POSIX paths, resolve to an existing unique source-path node or a files-surface node, preserve #symbol and ::test anchors as edge metadata. Do not stem-match paths.
- covered_by mixes child AC IDs and test paths. implemented_by mixes ticket and source paths. depends_on mixes hierarchy, pattern composition and dependency. Queries must distinguish endpoint kinds and must not claim a test verifies behavior from an untrusted declaration alone.
- ADR Markdown is canonical; its existing document identity and frontmatter stay intact. Component registry records and declared surfaces are canonical; graph hubs and file nodes are explicitly derived.
- No approved standalone Policy/Workflow/Decision/Lesson source schema has been established by this audit. Advertise unsupported operations where no mapping exists. An approved reviewed-Git extension or labeled synthetic corpus is necessary for correction/lesson precedent demonstrations. Kernel run records, trace observations and gap stores do not become Git history by copying them into Neo4j.
- Reject duplicate identities and required unresolved references before publication; preserve diagnostics for optional unresolved edges. Unknown kinds/relationship names must not acquire inferred meaning.

## Dependency and compatibility boundary

Canonical Git revision -> existing loaders -> knowledge projection ports -> Neo4j adapter.
Kernel capability -> thin integration adapter -> knowledge retriever port -> registered bounded queries -> serializable evidence -> existing kernel evidence contracts.

Knowledge core has no kernel/LangGraph imports. Driver, embedding and telemetry packages are optional adapters. Kernel config chooses the backend; no credentials occur in requests or evidence. Use the repository's Python modeling conventions, and have the source audit identify the smallest neutral reusable contract surface before changing shared models. Do not extract all kernel contracts merely to satisfy import neatness.

## Initial catalog and fixtures

Catalog candidates: get_entities; get_component_context; get_acceptance_criteria; get_related_tests; get_relevant_adrs; governing-policy lookup only for declared mappings. Memory operations get_previous_decisions, get_corrected_decisions, get_related_lessons, get_decision_evidence and semantic equivalents require the approved extension. Every entry declares scope, version, typed arguments, deterministic ordering, disclosure and work limits. Dynamic Cypher is excluded.

Use real KM-KGS-100a-3 and KM-KGS-100d-4 records plus their linked files/ACs for parser fidelity; use minimal reviewed immutable Git fixture commits for deletion, rename, failed-publication and scope-isolation tests. Semantic mechanics use fixed vectors and visibly synthetic history. Report a separate real-model evaluation rather than claiming semantic quality from synthetic vectors.

| Backend | Scope | Verification required |
|---|---|---|
| Disabled/null | Mandatory default; zero network calls | Fresh-process import and CLI without optional SDKs |
| Neo4j Community | MVP deployment candidate; float-list vectors and standard indexes | Pin server/driver matrix from official docs and execute all registered templates on real server |
| Aura | Optional alternative, not assumed equivalent | Verify deployed features/privileges and capacity before claiming support |
| Embedding adapter | Optional, model/version/dimension bound | Reject mismatch/non-finite values; prove changed text cannot reuse stale vectors |

No server version or live compatibility is claimed by this IT PO note. The implementer must append its source-symbol audit, actual versions, test commands and results before closing Stage 0 / release gates.

## Implementation partition

1. Foundation owner: neutral contracts, validation, configuration, null backend, registry, CLI and source audit.
2. Projection owner: immutable Git loader wrapper, mappings, migrations/manifests, publication, deletion/rollback and writer isolation.
3. Retrieval owner: Neo4j read adapter, exact/graph catalog, disclosure/cursors/source excerpts, optional vectors/hybrid and evaluation.
4. Integration owner: kernel port injection and mode decision, existing evidence conversion, correlated telemetry, merge workflow and runbook.

These are implementation ownership boundaries, not separate canonical domain models. KM-400 ACs are the requirement source. Technical metadata and test contracts are enriched after BA authors behavior; generated tickets derive from those ACs.

## Source audit closure (source/test lead, 2026-10-01)

The independent source investigator verified these symbols in the selected kernel-v0.1 base:

| Concern | Verified symbol | Integration consequence |
|---|---|---|
| Declared graph | scripts/knowledge_query.py NodeRecord (88), EdgeRecord (114), build_knowledge_map (437), validate_edges_integrity (657) | Reuse producer and config/paths.json declarations, preserving existing slug/stem/path IDs and AC-to-file/component edge directions |
| Invalid references | validate_edges_integrity drops missing targets | Immutable adapter must validate required AC depends_on references before filtering and report optional drops; a filtered graph alone does not prove source validity |
| Evidence | kernel/contracts/evidence.py Evidence, SourceVersion(commit, dirty), EvidenceBundlePayload; canonical evidence_id(locator, hash) | Neutral transport data maps only at the kernel adapter; retain content-addressed domain evidence and do not establish another domain Evidence model |
| Composition | kernel/bootstrap.py NATIVE_BINDINGS, build_bindings, EnvironmentOverrides | Inject retrieval implementation at existing composition seam |
| Invocation | kernel/capabilities/base.py CapabilityExecutor.ainvoke and frozen ExecutionContext | Use trusted registered capability and existing invocation context |
| Decisions | kernel/providers/base.py JevPort and QuestionSpec; kernel/capabilities/decision/jev_support.py ask_jev | Use existing provider abstraction and reserve-before-use accounting for ambiguous routing |
| Telemetry | kernel/observability/tracer.py Tracer; langfuse_tracer owns SDK | Create child observations through existing owner; knowledge must not instantiate Langfuse |
| Historical records | No approved Git Decision/Lesson source schema found | Demonstrate only explicitly synthetic reviewed extension fixtures; runtime persistence remains excluded |

Source parsers execute from the trusted installation, never from a scoped repository snapshot. Snapshots are data. This closes the source-symbol discovery gap of the initial IT PO inventory; actual implementation contract and real-server validation remain separate gates. The source/test lead owns executable RED tests and ticket generation.

## AC enrichment evidence

IT PO enriched all 25 BA-authored L2 records KM-400a-1 through KM-400e-5 with assigned-agent continuity, complexity, technical constraints, upstream/downstream contracts and two public behavioral/reachability test descriptors each. Protected BA fields were compared before/after and remained identical. The canonical validator inspected all 31 KM-400 YAML files and reported valid. No AC was marked implemented or done by this enrichment.

## Initial declared scope

The independent projection audit measured 97 colliding raw IDs across the legacy producer's surfaces (for example, agent entries and documentation stems). Therefore the initial production projection explicitly selects the canonical acs, components and adrs surfaces plus their declared file/test targets. It reports excluded surfaces in diagnostics and capabilities. It does not silently deduplicate, rename canonical IDs or pretend every legacy surface is supported. Duplicate IDs inside the selected scope remain publication errors. Synthetic memory is a separate, visibly labeled fixture extension. Wider surface support requires an approved identity mapping first.

## Final mapper 2 identity and provenance gate

The existing producer creates component hubs using registry IDs such as `knowledge_management`, alongside documentation-stem nodes such as `knowledge-management`. Mapper version 2 preserves both identities. A hub whose ID exists in `docs/components.json` receives that canonical source file, the exact `/components/{id}` JSON pointer and the whole-file content hash. Documentation-stem representations remain explicitly noncanonical; no mechanical underscore/hyphen rewrite establishes identity. Real `knowledge_management` level-3 retrieval resolved the registry section at immutable SHA `3299cc3ccb85f0cc767b968a56286416a08265f5`; evidence is saved in `reports/knowledge-retrieval-real-component-evidence.json`.

Optional-reference diagnostics compare both producer IDs and normalized source paths, preventing existing relative ADR file references from being reported missing. The explicitly selected ADR/component demo produced 121 nodes and 147 edges in separate scope `leafcutter-docs-demo`. The default full source remains blocked by three historical required references: ACS-200d -> ACS-200b, ACS-600e -> ACS-600b and ACS-600e -> ACS-300f. This subset does not establish validity of the full corpus.

## Full-corpus mapping review (mapper3)

Full AC-directory projection uses schema-validated canonical AC YAML records as primary AcceptanceCriterion nodes. Auxiliary Markdown documents such as PROJECT_CONTEXT.md are not AC identities; repeated stems are not deduplicated or renamed. Declared references to those files remain path-keyed SourceFile targets through the existing resolver. The optional producer filter preserves unchanged default behavior for other consumers.

The canonical `implemented_by` declaration has an AcceptanceCriterion source and may resolve to SourceFile, Test, ADR, Component or AcceptanceCriterion targets. Source review verified six legitimate instances beyond the earlier narrow target catalog: four component documentation artifacts delivering diagrams; GE-100's explicit GE-100h requirement reference; and UXP-700d-3-ii's changed UXP-515 YAML artifact. These remain `implemented_by` declarations with original direction/identity/provenance. They are not converted to dependency/coverage edges and do not independently prove fulfillment. Reverse non-AC sources remain invalid.
