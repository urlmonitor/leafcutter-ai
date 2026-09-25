---
title: "KI-KM-010 — The emission event is a receipt with no payload, and `_event_hash` keys on a field that is empty in every real record"
description: "KI-KM-010 — The emission event is a receipt with no payload, and `_event_hash` keys on a field that is empty in every real record"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-010 — The emission event is a receipt with no payload, and `_event_hash` keys on a field that is empty in every real record

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **PARTIAL** (verified 2026-09-25 against `main` @ `d2fe85a1`). **Fixed:**
  (1) the emission contract now carries `text`. It is required of producers and optional to
  consumers, in `signoff` §7 and in all three v3 templates (`468e0490`, #722). The
  placeholder fallback `event.get("text", f"[{entry_kind}] Learning from {ticket}")` is gone.
  A textless record is now classified `no_learning_text` (`d5fffdb1`, #650).
  (2) `ticket` vs `agent`+`component` is settled: `ticket` is optional and barred from
  identity, and the v3 templates defer to §7 (`48962ff5`, #649).
  (3) `_event_hash` is re-keyed on `_REQUIRED_DIGEST_FIELDS` =
  `(timestamp, agent, component, destination, entry_kind)`, and the collision test was added
  (`931b4beb`, #662). The 9 digest/idempotency tests pass.
  **Remains:** see the 2026-09-25 note at the end. The collision is narrowed, not closed.
  Two distinct learnings from the **same** agent and component, with the same day-resolution
  timestamp, still share one digest. The second learning is dropped as "previously processed".
  No other KI tracks this.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/skills/signoff/SKILL.md` §7 step 4 (the emitter contract);
  `scripts/knowledge/harvest_learnings.py` `_event_hash` and the `learning_text` fallback

**Symptom.** All 28 `knowledge_captured` events on disk share exactly one key set:
`event, timestamp, agent, component, destination, entry_kind`. There is **no `text`
field, and there never was one** — §7 step 4 specifies precisely these fields. The event
records that a write happened; it does not carry what was written.

The harvester was nonetheless built to route these events into knowledge surfaces, falling
back to `f"[{entry_kind}] Learning from {ticket}"` when `text` is absent. `ticket` is also
absent from all 28, so the fallback yields a trailing-space placeholder naming nothing.
`INF-400c-2`'s own Gherkin specifies three example events each carrying a *learning text* —
a shape that has never existed on disk. **The harvester was specified against an event
schema no emitter has ever produced.**

The durable anchor for the fallback is the string
`learning_text = event.get("text", f"[{entry_kind}] Learning from {ticket}")` — cite that
rather than a line number, which has already moved once.

**The second half: a hash keyed on nothing.** `_event_hash` builds its digest from
`(ticket, timestamp, destination, entry_kind)`. Since `ticket` is empty in every real
record, one of the four key components contributes a constant. Idempotency currently holds
only because the remaining three happen to differ — but **17 of the 28** timestamps are
day-resolution, so two learnings routed to the same destination with the same kind on the
same day would collide and the second would be silently treated as already processed.
Verified: the 28 records yield 28 distinct `(timestamp, destination, entry_kind)` triples,
so the corpus alone cannot demonstrate the bug — the collision must be constructed.

**A pre-existing contract violation nobody had noticed.** §7 step 4 documents an event
keyed on `ticket`; the three v3 agent templates (`product-owner.md:473`,
`business-analyst.md:911`, `it-po.md:812`) document `agent` + `component` instead. Every
one of the 28 on-disk records uses the v3 shape. `INF-400b-2` requires v3 emissions to be
"structurally identical" to §7 step 4's — that clause is **already violated in the shipped
artefacts**, and has been since both were written.

**Fix direction.** Three separable changes, and they must not be conflated:
1. Add a `text` field to the emission contract, additively — required of producers,
   optional to consumers, so the 28 six-field records stay structurally valid and simply
   classify as ineligible-to-write. All four emission surfaces (§7 step 4 plus the three
   v3 templates) change in one commit or the parity clause breaks further.
2. Reconcile §7 step 4 against the v3 templates so `ticket` versus `agent`+`component` is
   settled one way. This is `INF-400b-2`'s to own; it needs amending either way, because
   its enumerated field list goes stale the moment `text` ships.
3. Re-key `_event_hash` on fields that are actually populated, and add a collision test
   using two same-day same-destination same-kind records. Guard the over-correction too:
   hashing the whole record restores discrimination and destroys idempotency.

**Trap.** The hash defect is invisible today — no collisions exist among the 28 (verified).
It becomes reachable the moment emissions resume at any volume, which is exactly when the
loop is repaired. Fix it *with* the repair, not after.

**Related.** `KI-KM-009` (the false premise this schema misled). `INF-400b-2-i` and
`INF-400b-2-ii` (the owning ACs, authored 2026-08-26). `INF-700b-1` (requires the record to
carry the learning text).

**Verification note, 2026-09-25 — the residual collision.** Fix direction 3 asked for a key
on populated fields. Its guard was that hashing the whole record would destroy idempotency.
The re-key adds `agent` and `component`, but three things keep the original hazard alive.
First, `text` is deliberately excluded from identity. Second, §7 now fixes `destination` and
`entry_kind` to the sentinels `"(unrouted)"` / `"unclassified"`, so for every new emission
only `timestamp`, `agent` and `component` discriminate. Third, `timestamp` is specified only
as `<ISO-8601>`, so day resolution is still allowed.
The collision test (`TestTwoSameDaySameDestinationSameKindRecordsAreBothProcessed`) uses two
*different* agents, so it cannot see this case. A probe, run from the repo root, gave these
results:
- Two records with the same `agent`, `component` and `timestamp="2026-09-25"`, and different
  `text`, gave `_event_hash(a) == _event_hash(b)` → `True`.
- With a routable kind and two harvest runs, run 2 reported `routed 0, previously_processed 2`.
  Only `Learning A` was captured, so `Learning B` was silently dropped.

To close this, either require sub-second or monotonic timestamps from producers, or add a
content-derived discriminator (e.g. a digest of `text`) to the identity key. Then add a
same-agent collision test.

---
