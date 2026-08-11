---
title: "knowledge-management — event-refreshed read-index acceptance criteria"
date: "2026-08-11"
time: "18:29"
type: ac_authoring
components:
  - knowledge_management
  - ac_store
summary: "Authored and approved 16 L2/L3 acceptance criteria for an event-refreshed, self-healing read index over the cross-surface knowledge graph (first slice: scripts/knowledge_query.py), under existing L1 KM-KGS-100b."
description: "AC-store-only change (no implementation). Behavioral decomposition of a caching read-index capability whose core invariant is that the index is a self-healing cache, never a source of truth — a missed refresh event degrades to slower-not-wrong. Covers: index-backed read equals live full parse (KM-KGS-100b-5, render_json byte-parity -5-i, real-store deployed-layout verification harness -5-ii); mandatory stat-only staleness check every read (-6) with HEAD-sha/max-mtime short-circuit (-6-i); shared surface-scoped rebuild-on-read primitive (-7); missed-event slower-not-wrong safety (-8); missing/corrupt index live-parse fallback (-9); feature flag default-OFF no-op (-10, reader-first -10-i); project/output-root path anchoring for deployed + worktree layouts (-11, per-worktree atomic cache -11-i); and proactive refresh via post-commit git diff-tree, build-tail, and SessionStart (-12 + -12-i/-ii/-iii). Also fixes pre-existing enum drift by adding knowledge_management to the components enum in config/ac_store_schema.json (defined in docs/components.json and used by the existing KM family but missing from the schema enum, which blocked committing any knowledge-graph AC)."
pr: 408
breaking: false
---

## Entry

Adds the approved acceptance-criteria backlog (priority: medium) for the knowledge-graph read-index optimisation. Implementation is a downstream `/build-ac` step; the test contract requires behavioral verification against a real on-disk store in a deployed (`build.py --target-dir`) layout, not synthetic fixtures.
