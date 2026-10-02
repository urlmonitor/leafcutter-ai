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
