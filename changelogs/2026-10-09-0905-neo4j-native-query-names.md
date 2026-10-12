---
title: "Remove legacy Neo4j compatibility and update saved native queries"
date: "2026-10-09"
time: "09:05"
type: fix
components:
  - knowledge_management
summary: "Use native Neo4j graph and catalog formats exclusively, and replace both actual saved-query catalogs with freshly verified native entries."
description: "Remove legacy query rewriting, compiler-v1 reconstruction and old-graph conversion paths. Preserve native inspection and scoped publication safeguards, reject obsolete catalog versions and pins, and record the verified saved-query cutover."
tickets:
  - tickets/00_inbox/TICKET-20261009-KM-400a-3-i-native-query-maintenance.md
---

Queries use the physical domain labels and relationship types directly, including
`AC`, `ADR`, `Repository`, `Snapshot`, `COMPONENT_MEMBERSHIP` and `COVERED_BY`.
The package no longer carries a legacy compiler or a generic-graph conversion
path. Native graph inspection, refresh and publication retain their safety checks.

Both discovered application catalogs for `get_component_tests` were replaced
with freshly verified native entries. Each retained its one descriptor and
operation version; its compiled digest changed and the old pin is rejected.
Verification used the original retained Aura source and passed positive, empty,
invalid-input, injection and foreign-scope cases. Private backups preserve the
original bytes. The sanitized report records relative catalog identifiers,
old/new file hashes and the digest mapping without credentials or private paths.

Historical receipts remain evidence for their original runs. They are not loaded
as serving catalogs or presented as proof of the new compiled queries. Aura graph
data was unchanged by the saved-query replacement. Documentation describes the
native-only contract and the completed two-catalog cutover.

Verification passed 78 focused compiler/catalog tests, nine adapter unit tests,
15 refresh recovery cases and 19 checks on disposable Neo4j. Both actual catalogs
also passed positive and empty public retrieval after reopening in a fresh process.
Changed-file lint and annotation checks passed; no full pytest suite ran.
