---
title: "KI-ACS-20261014-untagged-done-ratchet-counts-composites-as-untested — the KM-ADM-005 ratchet requires a `# covers:` tag naming a composite AC itself, although the required done-proof gate proves a composite through its children, so marking a fully tested parent done fails the required pytest check"
description: "medium — test_untagged_done_ac_backlog_does_not_grow counts every work_status: done AC whose own id appears in no `# covers:` tag. A composite (an AC whose covered_by lists child ACs) is proved by its leaves under BO-2500a-6, so it normally has no tag of its own. Marking one done therefore grows the count. On PR #1199 that pushed it from 244 to 245 and failed the required pytest check, although both children of BO-3800a had passing tagged tests. The only way through is a redundant parent tag on a child's test, which adds no evidence."
type: reference
category: reference
status: active
created: '2026-10-14'
last_updated: '2026-10-14'
components:
  - ac_store
  - testing_quality
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
  - docs/known-issues/ac-store/open-high-ki-acs-20260914-composite-proof-drops-path-leaves.md
---

# KI-ACS-20261014-untagged-done-ratchet-counts-composites-as-untested — two definitions of "a done AC has a test"

> Filed 2026-10-14 at BrainCandy's request. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Work can land, but only by adding a tag that proves nothing. Until then
  the required `Test suite (pytest)` check is red for a correct change, and the failure is
  attributed to whichever PR happens to cross the mark.
- **Status:** open, no AC. The rule decided on 2026-10-14 (BrainCandy) is that **a top-level
  (composite) AC should not need its own tests when its children have them.**
- **Occurrences:** 1 failing CI run, plus 1 pre-empted.
  - **PR #1199 (BO-3800a), first CI run, 2026-10-14, shard 4/8.** The failure was
    `AssertionError: untagged-done AC backlog grew to 245, exceeding HIGH_WATER_MARK=244`. The
    trigger was the composite BO-3800a being marked done; its children BO-3800a-1 and -2 both had
    passing tagged tests.
  - **PR #1214 (BO-3800e).** This was pre-empted by tagging two child tests `# covers: BO-3800e`
    before the composite was marked done.
- **First seen:** 2026-10-14 · **Last seen:** 2026-10-14
- **Where:**
  - The ratchet is in `unit_tests/docs/test_artifact_graph_covers_scope.py` (AC KM-ADM-005).
    `HIGH_WATER_MARK = 244` is at :53. `_collect_done_ac_ids` (:156-168) collects every
    `work_status: done` id. `_collect_covers_tagged_ids` (:171-195) collects every `covers:`
    token. `test_untagged_done_ac_backlog_does_not_grow` (:198-220) asserts that
    `len(done - tagged) <= 244`. It never reads `covered_by`.
  - The required gate is in `scripts/ac_store/done_proof.py`. The composite-vs-leaf rule is
    documented at :17-25 (BO-2500a-6). A composite is decided by `_has_resolvable_child` (:1445)
    and proved through its leaves by `_resolve_all_child_ids` (:1470-1514) and
    `_verify_composite_eligible`.

## Symptom

A PR that marks a composite AC done, with every leaf below it done and tagged, fails the required
pytest check with:

```text
FAILED unit_tests/docs/test_artifact_graph_covers_scope.py::test_untagged_done_ac_backlog_does_not_grow
AssertionError: untagged-done AC backlog grew to 245, exceeding HIGH_WATER_MARK=244. A new
work_status: done AC was added without a `# covers: <id>` tagged test.
```

The same PR passes check-done-proof and the required Proof-of-done CI check, because those prove
the composite through its children.

## Mechanism

1. Under BO-2500a-6, a composite AC is proved by its leaf descendants. It needs no
   `# covers: <composite-id>` tag, and normally has none.
2. The KM-ADM-005 ratchet predates that rule. It treats a done AC as tested only when its own id
   appears in some `# covers:` tag.
3. So every composite marked done adds one to the ratchet's count, however well its children are
   tested. When the count is already at the mark, the next composite fails CI.
4. Whether a given PR fails depends on how much headroom other merges left. BO-3800c and BO-3800d
   were marked done on 2026-10-12/13 with no parent tag and passed. BO-3800a crossed the mark two
   days later. Those two composites are still counted as untested.

## Detection

A `test_untagged_done_ac_backlog_does_not_grow` failure whose "new ids" include an AC with a
non-empty `covered_by` of real child ids.

## Workaround (used on #1199 and #1214)

Add a second line, `# covers: <composite-id>`, to a child test that genuinely proves the parent's
promise end to end. On #1214 that meant one test per half of the promise. Don't add the tag to an
arbitrary test, and don't un-mark the composite.

## Suggested fix

- **Make the ratchet use the gate's definition.** Count a done composite as tested when every leaf
  its `covered_by` resolves to is tagged. Reuse `done_proof`'s `_has_resolvable_child` and
  `_resolve_all_child_ids` rather than re-deriving the tree, so the two cannot drift again.
- **Lower `HIGH_WATER_MARK`.** Composites currently counted would fall out of the backlog, so
  lower the mark to the newly measured value. Otherwise the freed headroom lets real untested
  leaves in.
- **Remove the redundant parent tags** added as workarounds once the fix lands. They are on
  `test_bo_3800a_2.py` (`# covers: BO-3800a`) and on `test_bo_3800e_1.py` and
  `test_bo_3800e_2.py` (`# covers: BO-3800e`).
- **Fix it in an AC.** Author it under KM-ADM-005's owner, since the ratchet is that AC's
  regression floor.

**Related.** `KI-ACS-20260914-composite-proof-drops-path-leaves` is another disagreement about
what a composite's children are, on the gate side.

**Pattern:** two checks answering "is this done AC tested?" with different definitions. The
stricter one rejects what the authoritative one accepts.
