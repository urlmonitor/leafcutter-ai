---
title: "KI-ACS-006 — Three defects in the done-proof oracle that misreport AC coverage"
description: "KI-ACS-006 — Three defects in the done-proof oracle that misreport AC coverage"
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

# KI-ACS-006 — Three defects in the done-proof oracle that misreport AC coverage

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/done_proof.py` (`_verify_composite_eligible`,
  `_resolve_all_child_ids`); `scripts/ac_store/test_enforcement.py` (`COVERS_TAG_RE`)

All three found by running the real oracle over the store rather than reading it. Context
for why they stayed hidden: CI runs `check_done_proof --mode ci-changed`, which only
evaluates ACs in the diff. The whole-store mode (`--mode ci`, `check_all_done_acs`) has
never run in CI, so none of these ever produced a visible failure.

**D-1 — the composite path ignores a child's `test_required: false`.**
`check_all_done_acs` honours the exemption for the AC it is evaluating, but
`_verify_composite_eligible` never reads the field when checking children —
`_build_ac_status_map` does not even carry it, so the function structurally cannot. A
composite whose only uncovered children are legitimately test-exempt can therefore never
be eligible. Live: `verify_done_eligible('BO-2300a')` → `composite BO-2300a has uncovered
children: BO-2300a-3`, where `BO-2300a-3` is a state-diagram AC with `test_required:
false` whose diagram exists at
`docs/architecture/diagrams/c3-001-interactive-pause-resume-run-lifecycle.md`. Three ACs
are stuck this way: `BO-2300`, `BO-2300a`, `BO-2300d`.

**D-2 — a legacy `covered_by` entry makes a child vanish.** `_resolve_all_child_ids`
recurses on `if child_covered_by:` — truthiness — instead of checking whether any entry
resolves to a store record. The legacy-path guard (`_has_resolvable_child`, the BO-2500a-6
M-2 remediation) is applied by the top-level caller but not at each recursion step. A child
whose own `covered_by` holds only a legacy test-file path is treated as a composite with no
leaves and contributes nothing, so the parent reports "no coverable children" instead of
naming the real untested child. Live: `BO-510-3.covered_by = ['BO-510-3-i',
'unit_tests/test_agent_produces_validation.py']` and `BO-510-3-i.covered_by =
['unit_tests/test_agent_produces_validation.py']` → `composite BO-510-3 has no coverable
children`. The correct verdict names `BO-510-3-i`.

**D-3 — multi-id `covers:` tags are mis-parsed.** `COVERS_TAG_RE` captures a single
`(\S+)`, so a line naming two ACs swallows the comma into the first id and drops the
second. `# covers: BO-610-1, BO-610-3-i` registers the id `'BO-610-1,'` — which matches
nothing and is also reported as a dangling tag — and `BO-610-3-i` is not registered at all.
`BO-610-1` and `BO-610-2` were both `work_status: done` with passing tests and the oracle
reported "no linked test found" for each. Partially mitigated on 2026-08-18 by splitting
the two affected tag lines one-id-per-line; **the regex is unchanged**, so the trap is live
for the next author. Two more occurrences remain in
`unit_tests/test_generate_ticket_from_ac.py` (`BO-530`, `BO-560`), harmless today only
because those ACs are `todo`.

**Why it matters.** D-3 produces false "untested" verdicts on ACs that are genuinely
covered, which is how a correct record gets flipped backwards. D-1 and D-2 make four ACs
permanently ineligible. Together they mean the whole-store sweep cannot be turned on: it
would block every merge on defects in the gate rather than in the store.

**Fix direction.** D-3 first — smallest, and it is the one currently producing wrong
verdicts. Then D-1 (pass `test_required` through `_build_ac_status_map` and honour it in
the composite path), then D-2 (apply `_has_resolvable_child` at each recursion step). Each
changes a gate's verdict, so each wants an AC and a test. Worth pairing with a decision on
whether `--mode ci` should run in CI at all — it currently cannot pass.

**Related:** a fourth defect in this family lives in `commit-guardian` — see KI-CG-006 for
the pre-commit variant being stricter than the CI backstop. A fifth is definitional: the
schema hook's `_is_leaf_ac()` treats any `level: L2` AC as a leaf, while the oracle treats
an AC with resolvable children as a composite, so the two gates can demand contradictory
things of the same record (observed on `BO-1500a-1`, `BO-1500b-1`, `BO-1500c-1`). Two more
live one layer lower, in how the oracle maps a tag to a test at all — see KI-ACS-008.

---
