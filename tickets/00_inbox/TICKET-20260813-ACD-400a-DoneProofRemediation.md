---
title: "Correct ACD-400a's overstated work_status and repair its covered_by back-links"
status: todo
components:
  - ac_driven_dev
  - ac_store
created: 2026-08-13
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: docs
risk_surface: internal
roadmap_phase: phase_1
files_touched:
  - docs/acceptance-criteria/ac-driven-dev/ACD-400a.yaml
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
tags:
  - ac-store-hygiene
  - proof-of-done
  - phantom-done
---

# Correct ACD-400a's overstated work_status and repair its covered_by back-links

## Actor / Goal

In order for the proof-of-done gate (`BO-2500b`) to mean what it says, we need
`ACD-400a`'s store record to stop claiming `work_status: done` while four of its
leaf descendants are `todo` and untested — so that the AC store reflects reality
and the outstanding `covered_by` back-links can land without re-tripping the gate.

## Context

### How this surfaced

During PR #424, `ACD-400a-3` and `ACD-400a-4` back-links were added to
`ACD-400a.covered_by` (those children arrived in `e34dc29da` / PR #418 without the
parent link). That edit pulled a `work_status: done` AC into the diff, so the
diff-scoped CI gate
(`check_done_proof.py --mode ci-changed --base origin/main`, CI job `done-proof`)
evaluated it and failed. The edit was reverted — `ACD-400a.yaml` is currently
byte-identical to `origin/main` (`git diff origin/main -- <file>` is empty) — and
a `[HOOK-SKIP: check-done-proof]` was recorded in commit `7c8c505e3`.

Two things are therefore outstanding: the **back-link repair** and whatever
honestly resolves the **done-proof question**. They must land together or in the
order given below, otherwise the back-link edit re-trips the gate exactly as it
did in #424.

Deliberately **not** done: authoring a test purely to satisfy the covers-tag check.
A test written to clear a done-proof gate is the phantom-done behaviour this repo
exists to prevent.

### The investigation — is ACD-400a genuinely done?

Three hypotheses were considered. **The evidence supports hypothesis 3: the
`work_status: done` claim overstates reality.** Evidence, in order:

**1. The gate already handles composites — no gate change is needed or wanted.**
`BO-2500a-6` ("A done composite AC derives its proof from its children, not from a
direct linked test") is `work_status: done` and its implementation is **live** in
`scripts/ac_store/done_proof.py`: `verify_done_eligible()` falls through to
`_verify_composite_eligible()` whenever the AC has no direct linked test but its own
`covered_by` resolves to real child records, and `_resolve_all_child_ids()` recurses
through child composites to leaf descendants. `templates/scripts/commit_guardian/check_done_proof.py`
imports that exact function. So the "missing `# covers: ACD-400a` tag" is a **red
herring** — the gate never asked for one.

**2. The real verdict names uncovered children, not a missing tag.** Running the
live gate against the current store:

```
verify_done_eligible('ACD-400a', ac_root=docs/acceptance-criteria, test_root=unit_tests)
-> {'eligible': False,
    'reason': "composite ACD-400a has uncovered children:
               ACD-400a-1-i, ACD-400a-1-ii, ACD-400a-1-iii, ACD-400a-2",
    'passing_tests': [], 'failing_tests': []}
```

**3. Those children are themselves `todo` with no implementation link and no test.**

| AC | title | `work_status` | `implemented_by` | `# covers:` tag |
|----|-------|---------------|------------------|-----------------|
| ACD-400a-1 | Leaf scanner filters to todo/active/unblocked L2/L3 and sorts by complexity then id | `todo` | — | none |
| ACD-400a-1-i | Empty ready list when no eligible files | `todo` | `[]` | none |
| ACD-400a-1-ii | Unparseable YAML reported as diagnostics without crashing | `todo` | `[]` | none |
| ACD-400a-1-iii | Circular dependencies detected without infinite loop | `todo` | `[]` | none |
| ACD-400a-2 | Scanner JSON output conforms to a schema with ready + blocked lists | `todo` | — | none |
| ACD-400a-3 | Ancestor is not a build-order blocker | `done` | yes | yes (`test_acd_400a_3.py`) |
| ACD-400a-4 | Fresh approved tree yields non-empty ready list end to end | `done` | yes | yes (`test_acd_400a_3.py`) |

A parent marked `done` whose declared children (`covered_by: [ACD-400a-1, ACD-400a-2]`)
are both `todo` is internally inconsistent **independently of any test question**.

**4. Hypothesis 1 (a covering test exists but is untagged) was checked and rejected.**
`unit_tests/` was searched for tests exercising `scan_ac_store.py` and
`ac_prioritizer.py`. The candidates all carry `# covers:` tags for *other* ACs and
cover *other* behaviour:

- `unit_tests/ac_store/test_leaf_filter.py` — all 10 tests tagged `# covers: ACD-1200a-10`;
  covers the `exclude_done` / `exclude_superseded` flags, not ACD-400a-1's
  level/status/unblocked filter or its complexity-then-id sort.
- `unit_tests/ac_store/test_scan_ac_store_cycle.py` — tagged `# covers: ACD-1200c-3`
  (cycle handling). Adjacent to ACD-400a-1-iii but authored against a different AC.
- `unit_tests/ac_store/test_tree_traversal.py` — tagged `ACS-1000`, `ACD-1200a-1`,
  `ACD-1200a-1-i`, `ACD-1200a-9-i`.
- Nothing anywhere asserts ACD-400a-2's JSON output schema.

So there is no untagged test that a tag could be retro-fitted to.

**5. What the L1's "own behaviour" is.** ACD-400a's four criteria lines decompose
cleanly onto its children: the leaf filter + sort → ACD-400a-1; the JSON/human
output with `ready` and `blocked` lists → ACD-400a-2. ACD-400a-3/-4 were added later
for build-order and end-to-end semantics. The L1 is a genuine composite with no
residual behaviour of its own, so a direct `# covers: ACD-400a` test would be
redundant even if the gate wanted one.

**6. The code exists; only the proof does not.** `scripts/ac_store/scan_ac_store.py`
implements every criterion — `_classify_ac()` (ready/blocked with named blockers),
the `estimated_complexity` then `id` sort, `_print_human()` / `_print_json()`,
`--json`. This is a *test and bookkeeping* gap, not a missing feature. That is why
the recommendation below is a status correction plus a backfill, not a rewrite.

### Recommendation

Correct the record now (this ticket), backfill the tests through the normal
AC pipeline (follow-on, out of scope here):

1. Set `ACD-400a.work_status` from `done` to `in_progress` — the honest value while
   its children are `todo`. This also removes it from the diff-scoped gate's
   evaluation set, since `check_done_proof` only evaluates changed ACs that are `done`.
2. In the **same edit**, add `ACD-400a-3` and `ACD-400a-4` to `covered_by`. With
   `work_status` no longer `done`, the back-link lands cleanly and the
   `[HOOK-SKIP: check-done-proof]` precedent is not needed again.
3. (Follow-on, separate tickets via `/build-ac`) Backfill tests for `ACD-400a-1`,
   `ACD-400a-1-i/-ii/-iii` and `ACD-400a-2` against the already-approved criteria.
4. (Follow-on) Once every leaf descendant has a passing `# covers:` test, flip the
   children to `done`, then `ACD-400a` back to `done`. The composite path in
   `done_proof.py` then passes it with **no gate change and no parent-specific test**.

## AC References

- No new AC is authored by this ticket. It remediates an existing store record against
  already-specified rules: `BO-2500b` (covers-tag presence gate) and `BO-2500a-6`
  (composite exemption). The behaviour still owed is specified by the existing
  `ACD-400a-1`, `ACD-400a-1-i/-ii/-iii` and `ACD-400a-2` records.

## Acceptance Criteria

- [ ] AC-1: `docs/acceptance-criteria/ac-driven-dev/ACD-400a.yaml` has `work_status: in_progress`
- [ ] AC-2: `ACD-400a.covered_by` equals `[ACD-400a-1, ACD-400a-2, ACD-400a-3, ACD-400a-4]`
- [ ] AC-3: No other field of `ACD-400a.yaml` is modified, and no other AC YAML file is touched
- [ ] AC-4: `python scripts/commit_guardian/check_done_proof.py --mode ci-changed --base origin/main` exits 0 on the branch with **no** `[HOOK-SKIP: check-done-proof]` in any commit message
- [ ] AC-5: `python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/ac-driven-dev/` passes
- [ ] AC-6: No production code under `scripts/` is changed and no test file is added or modified by this ticket

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Edit `ACD-400a.yaml`: `work_status: done` → `work_status: in_progress`
- [ ] Edit `ACD-400a.yaml`: append `ACD-400a-3`, `ACD-400a-4` to `covered_by`
- [ ] Run `validate_ac_schema.py` over `docs/acceptance-criteria/ac-driven-dev/`
- [ ] Run the done-proof gate in `ci-changed` mode against `origin/main` and confirm exit 0
- [ ] Confirm `git diff` shows exactly two changed lines in one file
- [ ] Open follow-on `/build-ac` tickets for `ACD-400a-1`, `ACD-400a-1-i`, `ACD-400a-1-ii`,
      `ACD-400a-1-iii`, `ACD-400a-2` (test backfill) and link them here

## Design Decisions

- **No gate change.** `BO-2500a-6`'s composite exemption is already implemented and live.
  The gate's refusal is *correct*: it named four uncovered children. Loosening it to accept
  a partially-covered composite would re-open the phantom-done hole `BO-2500` exists to
  close. Explicitly rejected.
- **No test authored to clear the gate.** A `# covers: ACD-400a` test written for no reason
  other than satisfying the check would be phantom-done by construction, and is redundant
  anyway: ACD-400a has no behaviour outside its children.
- **Status correction before back-link repair, in one edit.** Flipping `work_status` first
  takes ACD-400a out of the gate's `done`-only evaluation set, which is what lets the
  `covered_by` repair land without another `[HOOK-SKIP]`.
- **Flipping `work_status` off `done` is safe for build ordering.** `ACD-400a-1/-2/-3/-4`
  all list `depends_on: [ACD-400a]` (their own parent), which would normally mark them
  blocked once the parent is not `done`. `scan_ac_store.py`'s ancestor-aware
  `_get_ancestor_ids()` / `_classify_ac()` suppresses ancestor entries in `depends_on`
  — the very behaviour `ACD-400a-3` specifies, which is `done` and covered by
  passing tests. Verify this holds by running the scanner after the edit.

## Out of Scope

- Writing or tagging any test. The backfill for `ACD-400a-1`, `ACD-400a-1-i/-ii/-iii` and
  `ACD-400a-2` goes through `/build-ac` per AC, as separate tickets.
- Any change to `scripts/ac_store/done_proof.py`, `check_done_proof.py`, the CI `done-proof`
  job, or the `check-done-proof` pre-commit hook.
- Any change to `scan_ac_store.py` or `ac_prioritizer.py` — the implementation is present
  and correct; only its proof is missing.
- Flipping `ACD-400a` (or any child) to `done`. That happens only after the backfill.

## Risk & Safety

- Touches money? No.
- Touches data? Two field edits to one AC YAML record; fully reversible by `git revert`.
- Reversibility? Trivial — a two-line diff.
- Regression risk: moving `ACD-400a` off `done` makes it re-appear in "not yet done"
  reporting and in `ac_prioritizer` output. That is the intended, honest effect, not a
  regression. Its `L2` children are already `todo`, so ready-list contents do not change.
