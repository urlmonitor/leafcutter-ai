---
title: "KI-CG-20260914-done-proof-precommit-ignores-test-required — the pre-commit done-proof gate demands a covers tag from an AC that declares it needs no test, while the CI gate it stands in for exempts that AC"
description: "medium. The gate refuses a correct commit, and nothing a docs-only AC could honestly contain satisfies it. The two easy ways out are to write a synthetic `# covers:` tag or to leave the AC at `todo` after the work is done, and both make the"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-09'
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
- **Status:** open. The leaf half is fixed (PRs #861/#878). The composite half is still open; see Occurrences 2 and 3.
- **Occurrences:** 3 (hit 2026-09-14 while closing `UXP-700e-4`, a documentation-only AC, and with it its parent `UXP-700e`; 2026-09-28 closing `INF-1100d`, see Occurrence 2; 2026-10-09 closing `INF-700a`, see Occurrence 3)
- **First seen:** 2026-09-14 · **Last seen:** 2026-10-09
- **Where:** the original filing's line numbers are stale. On `origin/main` `4a5dfc1a5`, the composite half is in:
  - `scripts/ac_store/_done_proof_composite.py:194-268` `_unproven_composite_children()`. The leaf-child decision is at `:265-266`.
  - `templates/scripts/commit_guardian/check_done_proof.py:442-455`, the composite branch of `check_staged_done_proofs()`.
  - `scripts/ac_store/_done_proof_composite.py:302-328` `_verify_composite_eligible()`, which is CI's copy of the same check.

  See Occurrence 3 for details.

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

---

**Occurrence 3 — 2026-10-09: `INF-700a`, reproduced with the real hook; 10 composites in the store are now blocked this way.**

- **Severity:** unchanged at medium. The refusal is loud, not silent, so it does not meet `high`. The cost is a growing number of false `todo` composites, which Occurrence 2 predicted. Regrade it if a composite that must be closed for a release is among them.
- **Status:** open. Not fixed on `origin/main` `4a5dfc1a5`.
- **Occurrences:** 3. This is the third.
- **First/Last seen:** 2026-09-14 / 2026-10-09.
- **Where:** all three locations below were re-checked on `origin/main` `4a5dfc1a5`.
  - `scripts/ac_store/_done_proof_composite.py:260-266`. A done leaf child is proven only by `child_id_str in all_covered_ids`. If it is absent it goes onto `unproven` (`:265-266`), and `is_covers_tag_waived` is never consulted.
  - `templates/scripts/commit_guardian/check_done_proof.py:442-455`. The composite branch calls `_unproven_composite_children` and then `continue`s. The waiver call at `:458` is reachable only on the leaf path below it.
  - `scripts/ac_store/_done_proof_composite.py:315-317` (`_verify_composite_eligible`, CI). It reports any leaf descendant with no linked test as `uncovered_children`, with no waiver check. `check_all_done_acs` (`check_done_proof.py:539`) and `check_changed_done_acs` (`:614`) test the waiver only on the AC itself, never on its children.
  - The predicate that should be reused is `is_covers_tag_waived`, defined at `scripts/ac_store/_done_proof_phase_helpers.py:136-171` and re-exported from `done_proof.py:206`.

**Symptom.** `INF-700a` (`docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a.yaml`) cannot be flipped to `done`. All 5 children and every grandchild are `done`. Reproduced in a scratch worktree off `origin/main` `4a5dfc1a5`: `work_status` was flipped to `done`, staged, and the hook was run with `pre-commit run check-done-proof`. The hook reads the index, so the flip had to be staged. The deployed hook and the `templates/` source copy both refuse it verbatim:

```text
[check-done-proof] INF-700a: composite INF-700a is marked done but its covered_by children are not all done-and-covered — unproven: INF-700a-3, INF-700a-4
[check-done-proof] exemptions in force: 0
```

The flip was then discarded and not committed. `INF-700a-3` and `INF-700a-4` are docs-only: `work_status: done`, `test_required: false`, a non-empty `test_rationale`, and `implemented_by` naming the docs. `INF-700a` stays `todo` by its owner's decision until the gate is fixed.

**Cause.** As Occurrence 2 found, the waiver is honoured at the leaf level only. A child that passes `is_covers_tag_waived` still counts as "unproven" in the composite derivation. That holds in both the pre-commit copy (`_unproven_composite_children`) and the CI copy (`_verify_composite_eligible`).

**Other composites blocked the same way.** A read-only scan on `4a5dfc1a5` found 10 composites. The scan mirrored `_unproven_composite_children` over the whole store, once as written and once with the waiver applied to leaf children. Each composite below is not `done`, is refused only because of done, waived leaf descendants, and would pass if the waiver were honoured:

| Composite | `work_status` | Waived children reported unproven |
|---|---|---|
| `ACD-2100d` | todo | `ACD-2100d-4` |
| `ACD-2100e` | todo | `ACD-2100e-1`, `ACD-2100e-2` |
| `INF-1100d` | todo | `INF-1100d-2`, `INF-1100d-5` (Occurrence 2) |
| `INF-700a` | todo | `INF-700a-3`, `INF-700a-4` (this occurrence) |
| `INF-700c` | todo | `INF-700c-3` |
| `TQ-500f-4` | in_progress | `TQ-500f-4-i`, `TQ-500f-4-ii` |
| `UXP-542` | todo | `UXP-542-1` |
| `UXP-700a` | todo | `UXP-700a-5` |
| `UXP-700c` | todo | `UXP-700c-4`, `UXP-700c-5` |
| `UXP-700d` | todo | `UXP-700d-5` |

**Fix direction.** This is unchanged from Occurrence 2 and stated here as acceptance conditions.

- **Accept:** in `_unproven_composite_children` and in `_verify_composite_eligible`, count a child as done-and-covered when it is a leaf with `work_status: done` and `is_covers_tag_waived(child)` accepts it. That means `test_required` is exactly `False` and `test_rationale` is a non-blank string. Use the one shared predicate, not a third hand-written copy. In `_verify_composite_eligible`, drop waived leaves from `per_child_tests` before the `uncovered_children` check, and run tests only for the leaves that remain.
- **Keep refusing** when the waiver is not met:
  - a child that is not `done`;
  - a `test_required: false` child with an absent or whitespace-only rationale;
  - a child with `test_required` absent or `True` and no covers tag;
  - a composite with no AC-id children.
- **Tests:** add a pre-commit/CI parity test with one waived child and one non-waived child. Add a negative test where the only difference is a blank rationale.
- **Prove it on the store:** after the fix, the 10 composites above should each pass `pre-commit run check-done-proof` when flipped, and none should pass with the rationale blanked.

**Related.**
- `KI-ACS-006` D-1: the same omission, on the status-map side.
- `KI-ACS-20260914-composite-proof-drops-path-leaves`: another composite-derivation gap in the same function family.
- `KI-CG-013`: leaf/composite classification disagreement.
- BO-2500a-1-ii: the shared waiver predicate. BO-2500a-6: composite classification.

**Pattern:** an exemption fixed at the leaf level, with the derivation that aggregates leaves left unfixed. The aggregate's refusal message ("unproven") names the exempt children, so the gap reads as missing work rather than a gate defect.
