---
title: 'Aura knowledge deployment acceptance'
description: 'Verified KM-400 implementation outcomes and explicit deployment validation limits.'
type: explanation
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components:
  - knowledge_management
  - decision_kernel
---
# Aura deployment acceptance extension

Status: user-authorized full indexing and actual serving validation underway. This extends deployment evidence for existing KM-400 criteria; it does not add new production memory mappings.

## Reviewed source repair

IT PO reviewed BA's prerequisite amendment: ACS-200d replaces unresolved ACS-200b with ACS-100f, whose component/status query supplies the ticket rule's active-requirements lookup. ACS-600e replaces unresolved ACS-600b and ACS-300f with TKT-200a (generated component/data-flow diagrams) and ACS-300g (complete component registry). These are semantic prerequisite corrections, not historical renames. Existing criteria, titles and implementation states remain unchanged. Schema, dependency-cycle and immutable full-snapshot validation must precede Aura publication.

## Deployment gates and owners

1. BA repairs canonical references and records amendment rationale. Commit agent creates an immutable source revision containing approved repair and implementation; no merge is needed. Validate/plan default full supported surfaces at that exact SHA, with zero unresolved required references (KM-400a-1, b-1, b-2).
2. A explicitly binds authorized writer credentials through process-local WRITER variables and selected verified Aura database. Create only projector schema/indexes and publish the repository-scoped generation; replay the same SHA for idempotence. Record counts/SHA/generation/graph readiness and lag. Existing serving aliases must not silently become writer credentials (b-1, b-3, e-5).
3. A serves exact known/absent IDs, component context, related tests/ADRs and source-level pinned excerpts through actual configured factory/CLI. Compare canonical IDs/anchors and immutable source text; retain unsupported mapping status for production memory/policy (a-2, a-3, d-1, d-2).
4. C runs `tests/knowledge_live/aura_kernel_checks.py` with explicit KNOWLEDGE_AURA_SOURCE_SHA and repository identity. Actual KernelService and registered retrieval consume Aura evidence, complete a decision, reopen SQLite checkpoint and verify evidence SHA/retrieval provenance. Jev/host/human are deterministic doubles; Aura reads and Git source resolution are real. The test performs no Aura writes or provider calls (e-3).
5. Run targeted regressions for changed credential/database/source logic, canonical AC schema validation and normal repository enforcement separately from explicit-options pytest. Update acceptance/report outcomes with exact commands and report artifacts.

## Credential and embedding boundaries

The authenticated report verifies Aura5.27-aura read connectivity, explicit database selection and available vector procedures. It does not establish projector publication or vector-index readiness. Keep verified TLS; no trust bypass is required.

Writer-specific credentials are currently not configured. Existing user authorization for indexing supports explicit process-local binding of the authorized account for the indexing execution; keep that choice visible and secrets unprinted/unpersisted. If the same principal is used for serving and writing, report that limitation honestly. Separate variable names alone do not establish database-enforced least privilege; no permission-creation scope is inferred.

No embedding gateway endpoint/token configuration was found by a key-presence-only check. Current reviewed embedding eligibility is Decision/Lesson, while the canonical projection supports AC/ADR/component/path targets. Therefore full canonical publication alone cannot produce production semantic-history vectors. Do not send arbitrary source text to an unconfigured provider. Existing synthetic vector/hybrid proof remains separately labeled; configured-provider evaluation requires an approved eligible corpus and explicit model/dimension configuration.

No paid provider, account changes, broad cleanup, external workflow trigger, PR or merge is part of these validation gates.

## Repair validation result and next boundary

BA validated all4490 canonical AC records after the two-file amendment: schema and required references pass, with no new dependency cycle. Full projection then exposed a distinct mapping issue: repeated PROJECT_CONTEXT Markdown stems were entering the AC surface as if they were AC entities. Full Aura publication is not yet accepted. The appropriate existing a-1/b-2 boundary is to emit validated canonical AC YAML identities; non-AC context documents must be explicitly excluded/diagnosed or represented only as declared path-keyed source-file targets. No deduplication or invented ID renaming is permitted. The mapper owner must add a duplicate-context-file regression and rerun the immutable full preview before publication.

The full-corpus review also approved source-conformant `implemented_by` targets Component and AcceptanceCriterion alongside SourceFile/Test/ADR, retaining an AC-only source. Four referenced component diagrams and two canonical AC deliverables establish the need; no existing declarations are reclassified or interpreted as proof of completion. Positive target-kind and reversed-edge rejection tests gate this adjustment under existing KM-400a-1/a-3/b-2.

## Full-source preflight outcome

BA reports mapper3 full current-tree preflight passed:4490 canonical ACs,5989 nodes,19363 edges,92 diagnostics. The3 required references and4 malformed GE1074 pytest selectors are repaired; source mapping filters auxiliary Markdown and accepts declared Component/AC implementation targets. This preview is explicitly mutable and nonpublishable; actual immutableSHA validation and Aura publication are still pending. Source regressions12 passed6.20s and unchanged producer-consumer compatibility85 passed78.71s.
