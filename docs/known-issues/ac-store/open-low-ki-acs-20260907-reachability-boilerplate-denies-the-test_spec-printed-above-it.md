---
title: "KI-ACS-20260907-reachability-boilerplate-denies-the-test_spec-printed-above-it — the generated ticket tells the test author the AC declared nothing, six paragraphs below the six things it declared"
description: "medium — never blocks, and is wrong in the one direction that costs work:"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20260907-reachability-boilerplate-denies-the-test_spec-printed-above-it — the generated ticket tells the test author the AC declared nothing, six paragraphs below the six things it declared

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — never blocks, and is wrong in the one direction that costs work:
  it sends the reader looking for something that was never missing
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `_REACHABILITY_ASSERTS`
  constant at `:91`, consumed at `:1574` by the derived reachability descriptor

**What it does.** Every generated ticket carries one mandatory `angle: reachability`
descriptor on top of whatever the AC's own `test_spec` declared. That descriptor's assertion
text is a single module-level constant, and the constant states as fact:

```
The AC authored no test_spec, so the entry point is not declared:
resolve it before writing this test, and do not delete this entry.
```

It is emitted unconditionally. Confirmed by inspection: one definition at `:91`, one use at
`:1574`, and no branch anywhere on whether `test_spec` is present.

**Observed.** `TICKET-20260907-BP-100k-4-ii.md` was generated from an AC carrying **six**
behavioural `test_spec` descriptors. All six were carried into the ticket correctly, each
with its file, its `covers` list and its assertion — and the synthetic seventh descriptor,
in the same YAML block directly beneath them, told the reader the AC had authored none.

**Why this is not cosmetic.** The sentence is an instruction, and it instructs the wrong
action. A test author reading it is told that nothing in the store names the production entry
point and that resolving it is their first job. In this case the store named it plainly: the
AC's own constraints required verification against a built consumer layout, and every one of
its six descriptors specified execution as a process. The reader is sent to rediscover a
decision that had already been made and recorded — and the likeliest resolutions are to guess
a different entry point, or to conclude the entry is stale and delete it, which the same
sentence correctly calls the phantom-done path.

**How it got here, which is the interesting part.** The constant's own comment explains
itself: *"It is deliberately an instruction, not a stub: the AC authored no `test_spec`, so
nothing in the store names the production entry point."* The text was written for the
no-`test_spec` case and is correct there. What is missing is the branch — the case it was
written for became the only case it can express. A reasonable local decision generalised into
a false statement by being applied unconditionally.

**Fix direction.** Split the assertion in two and choose between them on whether the AC
actually declared a `test_spec`. When it did, say so and point at what it declared, so the
reachability floor builds on the AC's own entry-point statement instead of contradicting it.
When it did not, keep today's wording exactly — it is right for that case and its reasoning
about deletion should survive. Do not fix this by softening the text to something vague
enough to be true either way: an instruction that no longer tells the author what to do next
is worse than one that is occasionally wrong, because nothing surfaces the gap.

**Related.** The `framework`/`type` enum defect in `_test_descriptors_from_spec` (`:1451-1454`)
is the same function family and the same shape one layer along — a generator copying a
decision from a context that no longer holds. `BP-1100g-4-ii` closes the gate defect found in
the same incident; this is the other half of it, and is filed rather than fixed because the
two are independent and the gate one was blocking.

**Pattern:** boilerplate that was true of the case it was written for, promoted to
unconditional, so it now asserts the opposite of what the same document proves two
paragraphs earlier.

---
