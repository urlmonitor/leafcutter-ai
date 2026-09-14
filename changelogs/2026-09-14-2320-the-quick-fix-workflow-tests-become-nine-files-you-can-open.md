---
title: "The quick-fix workflow tests become nine files you can open"
date: "2026-09-14"
time: "23:20"
type: manual
components:
  - build_pipeline
summary: "test_quick_fix_workflow.py had grown to 1731 content lines against a 400-line limit, so it blocked its own commit and any change to one quick-fix test was gated by the size of its ninety neighbours. It is now nine files grouped by the phase each exercises, plus an uncollected harness, none over 317 lines. Nothing was dropped: 91 tests before and after, and the set of acceptance-criteria tags extracted from the new files diffs empty against the original."
description: "Splits unit_tests/workflows/test_quick_fix_workflow.py into _quick_fix_harness.py (136, shared fixtures, no test_ prefix so pytest does not collect it) plus test_quick_fix_worktree_invariant.py (317, BP-600a-1/a-2), test_quick_fix_guard_halts.py (177, BP-600a-3), test_quick_fix_ac_creation.py (184, BP-600b-*), test_quick_fix_red_phase.py (115, BP-600c-1/c-2), test_quick_fix_green_phase_and_mutation_proof.py (198, BP-600c-3), test_quick_fix_verification_trust_boundary.py (137, BP-600c-2), test_quick_fix_diagnosis_and_fix.py (175, BP-600d-1/d-2), test_quick_fix_commit_changelog_and_delivery.py (264, BP-600d-3/d-4) and test_quick_fix_escalation_and_topology.py (296, BP-600e-*). The .security-allowlist glob for the old path is moved onto the ten successors rather than dropped, since they are that file's contents and carry the same long-CamelCase test-class names that trip ENTROPY_HIGH."
commits:
  - af3aaa1c2
breaking: false
---

## Entry

### The gap: a file too big to change

`check-file-size` caps `.py` at 400 content lines. This file was at **1731**. That is
not a near miss — it meant the file could not be committed at all, so any edit to one
quick-fix test was blocked by the accumulated size of the other ninety.

The split is by **subject**, not by line count. Each file is named for the phase or
behaviour it exercises, so there is no `..._part2.py`: worktree invariant, guard halts,
AC creation, red phase, green phase and mutation proof, verification trust boundary,
diagnosis and fix, commit/changelog/delivery, escalation and topology.

### Proving nothing was lost

A split is the kind of change where a dropped test is invisible — the suite still passes,
just with less in it. So the claim was measured rather than asserted:

- **91 tests before, 91 after.**
- **Every `# covers:` acceptance-criteria tag survives.** The extracted tag multiset diffs
  *empty* against the original file, so no criterion silently lost its coverage. (One
  extra match appears for a prose occurrence — an assertion string containing the literal
  `"# covers:"` — which is not a tag.)
- Running the whole `unit_tests/workflows/` directory gives **629 passed / 25 subtests**
  on the branch and the **identical 629 / 25** on an unmodified worktree. Neither lost
  nor duplicated.

Total content rose 1731 → 1999 across ten files. That is the honest cost of a real split
— per-file module docstrings and import boilerplate — and it buys ten files a person can
actually open.

### The isolation trap this split deliberately avoided

The harness makes only additive, guarded `sys.path` inserts. It never touches
`sys.modules`.

That restraint is not incidental. Earlier the same day, a harness under
`unit_tests/commit_guardian/` evicted `build_phases` from `sys.modules` to force a fresh
import and never put it back. Four tests in `test_workflow_variant_transform.py` broke —
but only when both files ran in the same process. Each passed alone, every per-file run
was green, and it reached CI before anything noticed.

Splitting one file into nine that now always run together is precisely the situation
where such a leak surfaces, so the shared fixtures were written with no process-global
state to leak in the first place.

### Verification

All under `AC_ENFORCE_STRICT=1`, without which a failing test covering a not-yet-done AC
is downgraded to `xfail` and shows a false green.

- Each of the nine green standalone — 91 passed in total.
- All nine in one process: 629 passed, 25 subtests.
- Wider blast radius in one process, adding the four workflow-build suites:
  681 passed, 1 pre-existing xfailed, 25 subtests.
- Two explicit file-order permutations (full reverse, and a shuffle) to probe cross-file
  import-order coupling: 91 passed each.
- `ruff check` clean on all ten files.

One limitation is worth stating rather than glossing: **`pytest-randomly` is not installed
in this environment**, so true random-seed ordering was unavailable. The two manual
permutations are a weaker substitute. An earlier claim in this session that a run was
"clean under randomized ordering" was wrong for the same reason — `pytest -p no:randomly`
silently accepts an unknown plugin name, so what looked like two orderings was one.
