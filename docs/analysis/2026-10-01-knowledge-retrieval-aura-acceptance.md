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

Status: full immutable repository graph published; actual Aura kernel/checkpoint validation passed. Replay and standalone serving evidence are recorded by the projection owner. This extends deployment evidence for existing KM-400 criteria; it does not add new production memory mappings.

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

## Historical repair validation and resolved mapping boundary

BA validated all4490 canonical AC records after the two-file amendment: schema and required references pass, with no new dependency cycle. Full projection then exposed a distinct mapping issue: repeated PROJECT_CONTEXT Markdown stems were entering the AC surface as if they were AC entities. At this earlier preflight stage full Aura publication was not yet accepted; mapper3 subsequently resolved this boundary and the final outcome below supersedes it. The appropriate existing a-1/b-2 boundary is to emit validated canonical AC YAML identities; non-AC context documents must be explicitly excluded/diagnosed or represented only as declared path-keyed source-file targets. No deduplication or invented ID renaming is permitted. The mapper owner must add a duplicate-context-file regression and rerun the immutable full preview before publication.

The full-corpus review also approved source-conformant `implemented_by` targets Component and AcceptanceCriterion alongside SourceFile/Test/ADR, retaining an AC-only source. Four referenced component diagrams and two canonical AC deliverables establish the need; no existing declarations are reclassified or interpreted as proof of completion. Positive target-kind and reversed-edge rejection tests gate this adjustment under existing KM-400a-1/a-3/b-2.

## Full-source preflight outcome

BA reports mapper3 full current-tree preflight passed:4490 canonical ACs,5989 nodes,19363 edges,92 diagnostics. The3 required references and4 malformed GE1074 pytest selectors are repaired; source mapping filters auxiliary Markdown and accepts declared Component/AC implementation targets. This preview is explicitly mutable and nonpublishable; this historical preview was followed by the successful immutable publication recorded below. Source regressions12 passed6.20s and unchanged producer-consumer compatibility85 passed78.71s.

## Actual Aura kernel acceptance

The full supported canonical graph is published under repository `leafcutter`, immutable SHA `c2ddb6f126e5b8539f217836f67decba5e91eca4`:5992 nodes and19365 edges. Counts differ from the earlier mutable preview because committed proof metadata added three nodes and two edges. Publication followed the ordinary source commit with repository hooks; no push or merge occurred.

`tests/knowledge_live/aura_kernel_checks.py` passed **1 test in6.93s** against actual Aura. The real KernelService completed its decision and reopened SQLite checkpoint with two canonical evidence items, exact source SHA and retrieval references. Jev, host and human were deterministic doubles; Neo4j reads, Git excerpt resolution, kernel execution and checkpoint persistence were real. The test performed no database writes or embedding-provider calls. The sanitized artifact is `reports/knowledge-retrieval-aura-kernel.json`. Driver deprecation warnings were observed, with no test failure.

Command: `python -m pytest tests/knowledge_live/aura_kernel_checks.py -q --tb=short -o addopts='' -p no:cacheprovider --basetemp <temporary-directory>`, with explicit `KNOWLEDGE_AURA_SOURCE_SHA`, `KNOWLEDGE_AURA_REPOSITORY_ID=leafcutter` and the authorized external `LEAFCUTTER_ENV_FILE`. This direct pytest command disables repository addopts; it does not claim the AC-enforcement plugin ran. The ordinary source commit hooks passed separately.

Repeat sync and standalone retrieval also passed: same generation/counts, exact disclosure0–3, bounded component/AC graph results, related tests and ADRs, absent-ID empty success, and explicit unsupported production memory/policy. The detailed sanitized artifact is `reports/knowledge-retrieval-aura-publication.json`.
