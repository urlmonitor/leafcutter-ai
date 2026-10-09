---
title: "Use native graph names directly in Neo4j queries"
date: "2026-10-09"
time: "09:05"
type: fix
components:
  - knowledge_management
summary: "Remove legacy-name rewriting from current Neo4j operations while preserving previously admitted query receipts."
description: "Use native labels and relationship types in retrieval, publication, vectors and newly compiled catalog queries. Keep legacy names confined to explicit migration and immutable compiler-v1 receipt verification."
tickets:
  - tickets/00_inbox/TICKET-20261009-KM-400a-3-i-native-query-maintenance.md
---

The adapter sends its trusted Cypher unchanged to Neo4j. Current queries use the
physical domain labels and relationship types directly, including `AC`, `ADR`,
`Repository`, `Snapshot`, `COMPONENT_MEMBERSHIP` and `COVERED_BY`. Query arguments
remain separately bound and every operation retains its existing repository and
snapshot scope.

Newly admitted queries use compiler version 2. Previously admitted catalog entries
keep their exact compiled records, verification digests and public descriptor
identities; the version-1 compiler
is retained only to verify those historical records. Executing their descriptors
uses native Cypher. Old-format graph migration still recognizes its legacy labels
and relationships, and historical test receipts remain unchanged.

The retrieval guide explains the compatibility boundary and treats prior Aura
counts as source-pinned observations. This code cleanup does not claim a new Aura
publication or browser configuration change.

Focused validation passed 74 compiler/catalog cases, four adapter regression checks,
15 native-refresh recovery cases, and 16 cases against disposable local Neo4j.
The frozen historical compiler also matched the original implementation across
1,152 descriptor combinations. These are scoped checks; Aura was not changed.
