---
title: "KI-CG-20260914-done-proof-precommit-ignores-test-required — the pre-commit done-proof gate demands a covers tag from an AC that declares it needs no test, while the CI gate it stands in for exempts that AC"
description: "medium. The gate refuses a correct commit, and nothing a docs-only AC could honestly contain satisfies it. The two easy ways out are to write a synthetic `# covers:` tag or to leave the AC at `todo` after the work is done, and both make the"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-28'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260914-done-proof-precommit-ignores-test-required — the pre-commit done-proof gate demands a covers tag from an AC that declares it needs no test, while the CI gate it stands in for exempts that AC

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. The gate refuses a correct commit, and nothing a docs-only AC could honestly contain satisfies it. The two easy ways out are to write a synthetic `# covers:` tag or to leave the AC at `todo` after the work is done, and both make the AC store less truthful.
- **Status:** open
- **Occurrences:** 2 (hit 2026-09-14 while closing `UXP-700e-4`, a documentation-only AC, and with it its parent `UXP-700e`; 2026-09-28 closing `INF-1100d`, see Occurrence 2)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-28
- **Where:** `templates/scripts/commit_guardian/check_done_proof.py`: `check_staged_done_proofs()` (the pre-commit path, around line 586) and `_unproven_composite_children()` (around line 333). Compare with `check_all_done_acs()` (around line 737) and `check_changed_done_acs()` (around line 807), both of which skip `test_required: false`.

**Symptom.** A commit that marks an AC with `test_required: false` as `work_status: done` is refused:

```text
Check Done Proof (BO-2500b — covers-tag presence gate)....Failed
[check-done-proof] UXP-700e-4: no '# covers: UXP-700e-4' or '// covers: UXP-700e-4' tag found anywhere under .
[check-done-proof] UXP-700e: composite UXP-700e is marked done but its covered_by children are not all done-and-covered — unproven: UXP-700e-4
```

`UXP-700e-4` is `level: L2`, `change_target: docs`, `test_required: false`. Its `test_rationale` explains why a test would be the wrong proof. Its only implementation is a markdown reference.

**Mechanism.** The module has two code paths for the same rule, and they disagree on one condition. The CI paths (`check_all_done_acs`, `check_changed_done_acs`) both begin with `if data.get("test_required") is False: continue`. The fast pre-commit path, `check_staged_done_proofs`, has no such line. Nor does `_unproven_composite_children`, the helper it uses for composites. So the pre-commit gate is *stricter* than the gate it approximates. A fast approximation of a gate should never refuse what the authoritative gate accepts. When it does, the author is blocked locally for something CI would pass.

The composite half compounds it. A parent whose children are all done is refused because one child legitimately has no test. The only way to close the parent is to change the child.

**How it was worked around (and why that is not the fix).** A real test was added (`unit_tests/product_truth/test_uxp_700e_4.py`). It reads `product_truth_bounds.BOUNDS` and asserts the reference lists every declared bound, so it earns its place: it fails if a bound is added without updating the doc. But not every docs-only AC has an assertable relationship to code. The next one will face the same choice between a synthetic tag and a false `todo`.

**Fix direction.** Honour `test_required is False` in `check_staged_done_proofs` for leaves, and in `_unproven_composite_children` for children, exactly as the CI paths do. Keep "the Python boolean `False`, not a string" strictness, so one shared predicate serves all three paths. Add a test that feeds the same staged AC to both the pre-commit path and `check_changed_done_acs` and asserts they reach the same verdict. That test is what stops the paths drifting apart again.

**Related.** `ac-store.md` D-1 (the composite path ignores a child's `test_required: false`) is the same omission in the status-map derivation. The two should be fixed with one shared predicate, not two patches.

**Pattern:** two implementations of one rule, one "fast" and one "authoritative", with an exemption added to only one of them.

---

**Occurrence 2 — 2026-09-28: the leaf half is fixed, the composite half is not, and CI has the same composite gap.**
Reported by session leafcutter-6d (closed PR #928; carried over to main with its user's approval). `done_proof.py` line numbers re-checked on `ae85a2a1`; the `check_done_proof.py` ones are unchanged there.

Session observation: closing `INF-1100d` (L1, all nine children `done`) on the INF-1100d build branch was refused by pre-commit:

```text
composite INF-1100d is marked done but its covered_by children are not all done-and-covered — unproven: INF-1100d-2, INF-1100d-5
```

`INF-1100d-2` and `INF-1100d-5` are `test_required: false` with a `test_rationale` (verified on main `8ed47463`: both carry `test_required: false`; so does `INF-1100d-3`, a composite whose own children are covered). Workaround used: leave `INF-1100d` at `todo`, which makes the store less truthful. That is the outcome this entry's severity line predicted.

Verified in code on main `8ed47463`:

- **Leaf path: fixed since filing.** `check_staged_done_proofs` now calls `is_covers_tag_waived(data)` before refusing a leaf with no tag (`scripts/commit_guardian/check_done_proof.py:671-673`). The docstring states the scope on purpose: the exemption *"waives the direct-tag obligation; it does not waive a composite's child-derivation obligation"* (`:25-30`, `:588-615`).
- **Composite path: still open.** `_unproven_composite_children` (`:406-480`) proves a leaf child only by `work_status: done` **and** `child_id in all_covered_ids` (`:477-478`). It never calls `is_covers_tag_waived` on the child. So any composite with a legitimately exempt leaf child can never be committed as `done`. The docstring's reasoning covers a composite that declares `test_required: false` for itself (ACS-500g). It does not justify refusing a composite because a *child* is exempt.
- **CI matches this gap, so the two paths do not disagree here.** `check_all_done_acs` / `check_changed_done_acs` call `verify_done_eligible`, whose composite branch `_verify_composite_eligible` (`scripts/ac_store/done_proof.py:1729`) flattens to leaf descendants and refuses any leaf with no linked test (`per_child_tests` / `uncovered_children`, `:1774-1790`). It does not consult the waiver. The status map now carries `test_required` and `test_rationale` (`scripts/ac_store/_done_proof_phase_helpers.py:120-125`), so the data is available and simply unused. This is `KI-ACS-006` D-1, still live. `INF-1100d` would fail `ci-changed` with `composite INF-1100d has uncovered children: INF-1100d-2, INF-1100d-5`.
- **One asymmetry remains, in the other direction.** The CI functions test the waiver on the AC itself before anything else (`check_done_proof.py:753-755`). So a composite that is itself `test_required: false` with a rationale passes CI without its children being checked. Pre-commit evaluates the composite branch first (`:656-669`) and refuses it. That is the reverse of this entry's original complaint (pre-commit stricter than CI), on composites only.

**Fix direction, narrowed.** In both `_unproven_composite_children` and `_verify_composite_eligible`, treat a `done` leaf child that `is_covers_tag_waived` accepts as proven, and run tests only for the non-exempt leaves. Keep refusing a composite whose children are *all* exempt with no rationale, and keep the child-status check. Then decide once whether a composite's own `test_required: false` waives its child derivation, and make both paths follow that answer. The parity test from the original fix direction should include a composite with one exempt child.
