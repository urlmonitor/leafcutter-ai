---
title: "KI-ACS-20260914-composite-proof-drops-path-leaves — the CI done-proof gate expands a leaf that lists its test file in `covered_by` as if it were a composite, finds no children, and refuses every parent goal above such leaves"
description: "high. No L0 or L1 goal whose leaves record their tests in `covered_by` can be marked done, however complete its children are, and the refusal names no child to fix. On 2026-09-14 that was 476 ACs' worth of leaves, including every leaf in EP"
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

# KI-ACS-20260914-composite-proof-drops-path-leaves — the CI done-proof gate expands a leaf that lists its test file in `covered_by` as if it were a composite, finds no children, and refuses every parent goal above such leaves

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high. No L0 or L1 goal whose leaves record their tests in `covered_by` can be marked done, however complete its children are, and the refusal names no child to fix. On 2026-09-14 that was 476 ACs' worth of leaves, including every leaf in EPIC-TruthfulProjectRecord.
- **Status:** open. The goal it blocked, `UXP-700e`, was left at `todo` in #792 rather than have the gate fixed inside an unrelated change.
- **Occurrences:** 1 (CI on #792, 2026-09-14)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `scripts/ac_store/done_proof.py`: `_resolve_all_child_ids()` (around line 1379), called by `_verify_composite_eligible()` (around line 1616). Compare `_has_resolvable_child()` (around line 1354) in the same module.

**Symptom.** CI's `Proof-of-done coverage check (BO-2500b)` failed on a PR that marked `UXP-700e` done, even though its four children were done and every one had passing covers-tagged tests:

```text
python scripts/commit_guardian/check_done_proof.py --mode ci-changed --base origin/main --test-root .
[check-done-proof] UXP-700e: composite UXP-700e has no coverable children
```

With `UXP-700e` set back to `todo`, the same command exits 0.

**The data.** Each child lists its test file in `covered_by`, alongside any child AC ids. For example, `UXP-700e-4` has `covered_by: [unit_tests/product_truth/test_uxp_700e_4.py]`, and `UXP-700e-1` has `[UXP-700e-1-i, UXP-700e-1-ii, unit_tests/product_truth/test_uxp_700e_1.py]`. `docs/reference/ac-schema.md` documents this as valid: `covered_by` holds "Test file paths ... or direct-child AC IDs". 476 ACs in the store use it.

**Mechanism.** The module has the right predicate and one of its two call sites skips it. `_has_resolvable_child()` implements BO-2500a-6 remediation M-2: an AC whose `covered_by` holds only paths, none of which resolve to an AC record, is a LEAF. That is how the top-level AC is classified. But `_resolve_all_child_ids()` decides whether to recurse into each child with `if child_covered_by:`, meaning any non-empty list. A leaf with a test path in `covered_by` is therefore recursed into. The path is not a key in the status map, so it is skipped, and the leaf contributes nothing. When every leaf is shaped like that, the composite resolves to zero leaves and is refused as "no coverable children".

The pre-commit gate (`templates/scripts/commit_guardian/check_done_proof.py`, `_unproven_composite_children`) classifies children by `level`, not by `covered_by`, and passed the same commit. So local and CI verdicts disagree about the same AC. This is the same fast-versus-authoritative drift as `KI-CG-20260914-done-proof-precommit-ignores-test-required` (`commit-guardian.md`), with the opposite sign.

**Fix direction.** In `_resolve_all_child_ids()`, recurse only when `_has_resolvable_child(child_covered_by, ac_status_map)` is true. Otherwise append the child as a leaf. Pin it with a three-level fixture: an L1 whose L2 child lists a child L3 id plus a test path, and whose L3 lists only a test path, each with a passing covers tag. The L1 must be eligible. Run the fixture through both the CI path and the pre-commit path and assert they agree. Once fixed, mark `UXP-700e` done again.

**Pattern:** a module that defines the correct classification predicate and then re-derives the classification inline at a second call site, less carefully.
