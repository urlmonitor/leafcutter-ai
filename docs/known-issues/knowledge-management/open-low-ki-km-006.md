---
title: "KI-KM-006 — The artifact graph is a hand-authored type-level schema; no AC covers making it dynamic"
description: "KI-KM-006 — The artifact graph is a hand-authored type-level schema; no AC covers making it dynamic"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-006 — The artifact graph is a hand-authored type-level schema; no AC covers making it dynamic

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** open — no AC authored
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/reference/artifact-knowledge-graph.graph.json`; consumed by
  `leafcutter-web/lib/data/flows.ts`

**Symptom.** The graph describes artifact **types** and the relations between them. It
cannot answer an instance question — "show me this AC, its tests, its dependencies, and
what it changed" — because it holds no instance data and no generator produces it. Every
edit is by hand.

**Evidence.** No script under `scripts/` references the graph JSON; its only consumers
are `flows.ts`, `types.ts`, and one test.

**Prerequisite, not just effort.** A dynamic instance graph must carry each rendered
edge's trust rating from the type-level map, or it silently re-introduces the false
confidence that `KM-ADM-001` and `KM-ADM-005` were built to remove. The type map becomes
the schema the dynamic layer reads from — design it that way from the start.

**Precedent that this is buildable.** `UXP-421a` (done) already colours each Atlas flow
step live from the acceptance-criteria store, so live per-request store reads are proven
in this app.

---
