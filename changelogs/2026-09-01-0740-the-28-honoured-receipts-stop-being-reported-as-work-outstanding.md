---
title: "The 28 honoured receipts stop being reported as work outstanding"
date: "2026-09-01"
time: "07:40"
type: manual
components:
  - knowledge_system
  - infrastructure
summary: "Adds an `outstanding` count — records carrying real text that have not yet been written — so the real 28-record corpus reaches exit 0 with 0 outstanding, while the 28 remain visible as `no learning text` rather than hidden. The resting state is reached by a data-driven eligibility rule, not by an exemption keyed on the corpus."
description: "INF-700c-2 with its two constraints. The 28 knowledge_captured records on disk are receipts of writes that already happened, not pending work — INF-700c-1 established that a record with no learning text is ineligible to be written. This AC completes the consequence: an ineligible record is not OUTSTANDING either, so the figure an operator reads as 'work waiting' finally tells the truth over the real corpus. Verified end to end: 0 outstanding, exit 0, with all 28 still reported under `no learning text` and the malformed line at 19 still named. Nothing is moved, marked, archived or deleted; the corpus stays byte-for-byte in place and the resting state is a property of the data, so the next textless corpus in a consumer install inherits it with no edit. THE DEFECT THE REVIEW CAUGHT, AND WHY IT MATTERED: the fast lane's review phase blocked the commit with a high-confidence finding, and it was right. A record carrying real, non-empty text but MISSING one of _REQUIRED_DIGEST_FIELDS hit the `except KeyError` around _event_hash — added by INF-400b-2-i, merged roughly an hour earlier — and its `continue` fired BEFORE the outstanding-counting logic ran. So a genuine unwritten learning reported `outstanding: 0`, in the single figure this AC exists to make truthful. Reproduced directly: a record with entry_kind 'adr' and real text but no `agent` field printed '0 learnings routed: none; 0 outstanding; 1 record(s) missing a required digest field at line(s) [1]'. Twelve tests passed green on top of it because none constructed a text-bearing record with a missing field. Neither AC is wrong alone; the defect exists only in their composition, and appeared within an hour of the first one merging. Fixed by incrementing `outstanding` in that except branch when the record is not eligibility-excluded — INF-700c-2-ii's own it_requirements admit 'no floor, no cap, no exclusion by age, agent, kind or destination', and a missing digest field is exactly such an exclusion if the continue skips the count. Three cases now discriminate correctly: text-bearing and missing a field counts 1; textless and missing a field counts 0 (ineligible, not outstanding); the real 28-record corpus counts 0. A test plus its negative control were added and proved red with the fix removed — the pair matters because a version that incremented unconditionally would pass the positive case alone. The HarvestResult docstring is corrected too: it listed the exclusions from `outstanding` without mentioning missing_required_field_count, and while the sentence was literally true (such a record can never be hashed, so it can never be watermarked, and never reaches the write step) the silence is what let the defect look consistent with the documentation. It now states plainly that `outstanding` is NOT one of the six partitioning buckets — it overlaps them by design, and reading it as a seventh bucket is the mistake that produced the undercount."
breaking: false
---

## Entry

The 28 records on disk are **receipts of writes that already happened**, not pending work. `INF-700c-1` established that a record with no learning text is ineligible to be written; this completes the consequence — an ineligible record is not *outstanding* either.

Over the real corpus:

```
0 learnings routed: none; 0 outstanding; 28 no learning text: 2 agent-assignment-pattern,
5 agent-learning, 5 agent-memory, ... ; 1 malformed line(s) at [19]
exit: 0
```

**0 outstanding, exit 0** — and the 28 still *visible* rather than hidden. Nothing was moved, marked, archived or deleted. The resting state is a property of the data, so the next textless corpus in a consumer install inherits it with no edit.

### The review blocked this, and the defect was an hour old

A record carrying **real text** but missing one of `_REQUIRED_DIGEST_FIELDS` hit the `except KeyError` around `_event_hash` — added by `INF-400b-2-i`, merged roughly an hour earlier — and its `continue` fired *before* the outstanding-counting logic.

```
0 learnings routed: none; 0 outstanding; 1 record(s) missing a required digest field at line(s) [1]
```

A genuine unwritten learning, invisible in the one figure this AC exists to make truthful. **Twelve tests passed green on top of it**, because none constructed a text-bearing record with a missing field.

Neither AC is wrong on its own. The defect exists only in their composition.

### Three cases now discriminate

| Record | `outstanding` |
|---|---|
| text-bearing, missing a digest field | **1** |
| textless, missing a digest field | 0 — ineligible, not outstanding |
| the real 28 | 0 |

A test and its **negative control** were added, both proved red with the fix removed. The pair matters: a version incrementing unconditionally would pass the positive case alone.

### The docstring said nothing, and that was the problem

It listed the exclusions from `outstanding` without mentioning `missing_required_field_count`. The sentence was *literally* true — such a record can never be hashed, so it can never be watermarked, and never reaches the write step — but the silence is what let the defect look consistent with the documentation.

It now says plainly that `outstanding` is **not** one of the six partitioning buckets. It overlaps them by design, and reading it as a seventh bucket is the mistake that produced the undercount.
