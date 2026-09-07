---
title: "The idempotency digest stops keying on a field that is empty in every real record"
date: "2026-08-31"
time: "20:42"
type: manual
components:
  - knowledge_system
  - infrastructure
summary: "_event_hash keyed on (ticket, timestamp, destination, entry_kind) while `ticket` is absent from all 28 real records — one of four key components was a constant, and 17 of 28 timestamps are day-resolution, so two learnings to the same destination with the same kind on the same day would collide silently. Re-keyed onto the fields INF-400b-2-ii made mandatory."
description: "INF-400b-2-i, the code half of KI-KM-010. `_event_hash` built its SHA-256 over `(ticket, timestamp, destination, entry_kind)`, defaulting `ticket` to the empty string when absent. It is absent from every one of the 28 records on disk, so a quarter of the key contributed nothing. With 17 of 28 timestamps at day resolution, two learnings routed to the same destination with the same entry_kind on the same day produce an identical digest and the second is silently treated as already processed. Zero collisions exist in the current corpus (28 distinct triples, verified), which is why this was latent — it becomes reachable the moment emissions resume, i.e. exactly when INF-700b repairs the capture loop. Re-keyed onto `agent` and `component`, which INF-400b-2-ii (merged earlier the same day, PR #649) made required of every producer, with `ticket` demoted to optional. A record missing a required digest field now raises KeyError from `_event_hash`, caught by `harvest()` and counted in a new `missing_required_field_count` bucket rather than hashing to a degenerate value. TEST FALLOUT AND WHY THE HELPER WAS THE RIGHT FIX: 15 previously-green tests went red, and the fast lane's review phase blocked the commit over it — verified by stash-and-run rather than by reading the coder's own note, which had documented the collateral and shipped anyway. The cause was the shared `_make_event()` helper supplying `ticket` but never `agent`/`component` — the pre-INF-400b-2-ii shape. Unlike the `text` default deleted by INF-700c-1 earlier the same day, fixing this at the helper is correct: `text` absence is a meaningful classification, whereas `agent`/`component` absence is simply non-conformance with a contract this repo now ships. The helper now emits the conformant required set. A sixteenth failure was found by running the whole directory rather than the named list — `test_quality_improvement.py` built an event dict by hand with the same stale shape. THE BUCKET THAT ALMOST DID NOT COUNT: the new `missing_required_field_count` is the seventh bucket on HarvestResult and does correctly participate in the record total — every knowledge_captured record lands in exactly one of six record-level buckets. But the two pre-existing invariant tests assert a FIVE-bucket sum, written before this bucket existed, and pass only because the new bucket is always 0 in their scenarios. Neither would catch a regression where a record entered it and vanished from the total — precisely the 'a bucket that does not participate in a total is a bucket that can silently drop records' defect INF-700c-1 was written to prevent, reappearing two ACs later in the same file. Closed with an additive test that constructs one record of each of the six kinds and asserts the six-bucket sum, with the new bucket as an explicit term. 66 tests pass under AC_ENFORCE_STRICT=1."
breaking: false
---

## Entry

`_event_hash` keyed its digest on `(ticket, timestamp, destination, entry_kind)`.

`ticket` is absent from **all 28** records on disk, defaulting to `""` — so one of four key components was a constant. And **17 of 28** timestamps are day-resolution, so two learnings routed to the same destination with the same kind on the same day collide, and the second is silently swallowed as already-processed.

Zero collisions exist today (28 distinct triples, verified). That is why it was latent — and why it becomes reachable the moment emissions resume, which is exactly when `INF-700b` repairs the capture loop.

Re-keyed onto `agent` and `component` — the fields `INF-400b-2-ii` made **required of every producer** earlier the same day, with `ticket` demoted to optional.

### The review blocked this, and was right

15 previously-green tests went red. The fast lane's review phase refused the commit and verified it by stash-and-run rather than by reading the coder's own note — which had documented the collateral and shipped anyway.

### Why fixing the shared helper was correct here

`_make_event()` supplied `ticket` and never `agent`/`component` — the pre-`INF-400b-2-ii` shape. Those fixtures were emitting records non-conformant with the contract this repo now ships.

This is the **opposite** call from `INF-700c-1` earlier today, where adding a default to the same helper would have re-created the placeholder just deleted. The difference: `text` absence is a *meaningful classification*; `agent`/`component` absence is simply non-conformance.

A sixteenth failure turned up in `test_quality_improvement.py` — found by running the whole directory rather than the named list.

### The bucket that almost didn't count

`missing_required_field_count` is the seventh bucket, and it **does** participate in the record total correctly.

But the two pre-existing invariant tests assert a **five**-bucket sum — written before this bucket existed — and pass only because it is always 0 in their scenarios. Neither would catch a record entering it and vanishing from the total.

That is exactly the *"a bucket that does not participate in a total is a bucket that can silently drop records"* defect `INF-700c-1` was written to prevent, reappearing two ACs later in the same file. Closed with an additive test asserting the six-bucket sum with the new bucket as an explicit term.
