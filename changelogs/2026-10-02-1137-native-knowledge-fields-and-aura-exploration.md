---
title: "Expose complete native project metadata and readable types in Aura"
date: "2026-10-02"
time: "11:37"
type: feature
components:
  - knowledge_management
summary: "Neo4j exposes ACs, ADRs and 15 other native types with complete authored metadata, readable captions and declared-component filters."
description: "Preserve nested field identity, types, omissions and provenance; verify physical property readback before activation; safely resume interrupted metadata refreshes; retain existing generations and retrieval contracts. Add 17 type-specific acceptance criteria linked to existing tests. All 17 implementation criteria are done, including the glossary escape test verified on Linux. Provide isolated Neo4j services for the CI proof-of-done gate."
tickets:
  - tickets/00_inbox/TICKET-20261002-KM-400a-3-i.md
---

The PR includes the earlier standalone knowledge retrieval and governed query
foundation on which native metadata projection depends. The database remains a
rebuildable projection of an immutable repository revision.

The native-branch integration compared every current native record with its authored
source instead of assuming fixed corpus sizes. Glossary paths reject Windows absolute,
drive-relative, UNC and parent escapes on every host. The completion gate uses
an isolated real Neo4j query-growth proof; hosted Aura verification remains an
explicit supplemental probe. The full pytest CI job remains disabled as requested.

The async-aware proof scanner keeps the Aura deployment smoke check separate from
KM-400e-3, whose approved contract explicitly requires an offline fake-port proof.
Its existing public-kernel test remains linked and runs without hosted credentials.

The native branch retrieval-only kernel fixtures explicitly disabled optional host
synthesis instead of depending on a changing repository default. Their public invocation, evidence,
checkpoint and query-reuse assertions remain intact; research-policy tests retain
synthesis coverage.

The integrated retrieval release preserves reviewed exact source censuses together
with the incoming manifest, render-byte and epic-source assertions. Its kernel
fixtures consume actual synthesis evidence packets under the repository default
before the original completion and reuse assertions; the local real-Neo4j proof
also verifies refusal and persisted verification digests. Earlier native-branch
execution records remain historical and are not relabeled as this integration.
