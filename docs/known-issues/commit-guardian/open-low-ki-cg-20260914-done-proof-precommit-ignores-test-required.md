---
title: "KI-CG-20260914-done-proof-precommit-ignores-test-required — the pre-commit done-proof gate demands a covers tag from an AC that declares it needs no test, while the CI gate it stands in for exempts that AC"
description: "medium. The gate refuses a correct commit, and nothing a docs-only AC could honestly contain satisfies it. The two easy ways out are to write a synthetic `# covers:` tag or to leave the AC at `todo` after the work is done, and both make the"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
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
- **Occurrences:** 1 (hit 2026-09-14 while closing `UXP-700e-4`, a documentation-only AC, and with it its parent `UXP-700e`)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
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
