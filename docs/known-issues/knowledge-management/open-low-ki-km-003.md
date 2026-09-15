---
title: "KI-KM-003 — The map understates `ticket-touches`: config flipped to strict, the rating and both notes did not"
description: "KI-KM-003 — The map understates `ticket-touches`: config flipped to strict, the rating and both notes did not"
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

# KI-KM-003 — The map understates `ticket-touches`: config flipped to strict, the rating and both notes did not

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/reference/artifact-knowledge-graph.graph.json` (edge `ticket-touches`);
  `templates/scripts/commit_guardian/commit_guardian.json` (hook `_comment`, and the
  `files_touched_reconciliation` section)

**Symptom.** `files_touched_reconciliation.strict` is now `true` on main, so undeclared
source files **block** a ticket commit. But the graph JSON still rates the edge
`enforcement: "warn"` and its note still reads "advisory: files_touched_reconciliation.enabled
true, strict false … Flipping strict:true promotes this edge to 'enforced'." A reader of
the map concludes the edge is advisory when it now blocks.

**Second, same drift, different file.** The hook's own `_comment` in
`commit_guardian.json` still says "Advisory by default (… strict: false)" while the
`files_touched_reconciliation` section eight hundred lines below sets `"strict": true`.
The config contradicts itself.

**Why the guard did not catch it.** `unit_tests/docs/test_artifact_graph_trust_ratings.py`
derives expected enforcement from **hook registration** in `commit_guardian.json` — which
is exactly right for `KM-ADM-001`'s purpose, and is why `ac-tested` was correctly
demoted. It contains zero references to `strict`, so a registered hook that changes from
advisory to blocking is invisible to it. The rating drifted inside 24 hours of the parity
test shipping.

**Note the direction.** The map is wrong conservatively — it under-claims trust. That is
the safe direction, and it is still drift: the whole point of the ratings is that a
reader can act on them.

**Suggested fix shape.** Extend the trust-ratings test to read the three-state config
(`enabled` / `strict`) for hooks that have one, not just registration. Then correct the
rating, the note, and the stale `_comment` together.

**Candidate home when it earns an AC.** `KM-ADM-100a` ("a connection's trust rating
reflects what actually runs, and says how much it covered") — this is the same failure
class as `KM-ADM-001`, one config field deeper.

---
