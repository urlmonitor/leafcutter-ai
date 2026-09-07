---
title: A tree split is the one commit the AC back-link gate cannot see
date: "2026-08-26"
time: "16:15"
type: manual
components: 
  - build_pipeline
  - commit_guardian
summary: "BP-100k is split into two L1s and its child-limit waiver is discharged — and the split turned up a gate that reports a clean pass on every renamed acceptance criterion."
description: "Pattern C split of BP-100k (8 L2 children against a cap of 5) into BP-100k + BP-100n, removing child_limit_override: 9 rather than raising it. The three moved children share a rule sharper than the division guessed when the waiver was filed: an absence must be reported as an absence, never inferred to mean there is nothing to check. Also corrects BP-100's covered_by, which listed 7 of its 13 L1 children. Records KI-CG-20260826-1612: all six AC guardian hooks filter the index on --diff-filter=AM, which excludes renames, so the moved records were invisible to every gate meant to validate them — and renaming is exactly what the ac-tree-split skill mandates. Proven by controlled A/B, not inferred. No production behaviour changes; source edits are AC-ID traceability comments only."
---

## Entry

`BP-100k` had eight L2 children against a default cap of five, held open by a
`child_limit_override: 9` filed the day before with a note calling it temporary and naming
Pattern C as the honest fix. This discharges that waiver rather than raising it.

The waiver's note guessed the split would fall along manifest-completeness versus
gate-verdict-honesty. Reading the eight criteria together, it does not. Three of them share
something sharper:

- **the former `BP-100k-6`** — an output the build recorded writing but that is gone from
  disk must be reported, not passed over as an informational remark
- **the former `BP-100k-7`** — a capability whose output is absent must *not* be inferred to
  mean the capability is disabled; that inference is the failure the guard exists to catch
- **the former `BP-100k-8`** — a platform the guard never exercised must be named unverified,
  never counted as covered

One rule, three surfaces: **an absence must be reported as an absence, and never read as
"nothing to check here."** They become `BP-100n-1..-3` under a new sibling L1, `BP-100n`.
`BP-100k` keeps `-1..-5`, which are all about whether the comparison the drift gates perform is
sound, and now sits at exactly its cap with no waiver.

The cluster was also the cheapest of the candidates — 84 references across 17 files, no L3
children to cascade, and no edits to `changelogs/` or the known-issues register. That last point
decided it. A balanced 4+4 split was available and semantically defensible, but it cost 292
references across 46 files and would have rewritten acceptance-criterion ids inside two shipped
changelog entries and the known-issues register, falsifying the record of what shipped under
which id. A tidier tree is not worth an inaccurate history.

`BP-100`'s `covered_by` is corrected in the same change: it listed 7 L1 children while 13
existed on disk, with `d`, `e`, `f`, `g`, `h` and `l` never having been listed. Its
`child_limit_override` stays at **13** — unchanged, not raised. There are now 14 `BP-100x` files,
but `BP-100b` carries `status: superseded_by` and is excluded from the cap count, so the gate
counts 13 and the existing waiver already covers it. Leaving it exact means the next L1 added
trips the gate instead of sliding under a margin.

## The gate that could not see the split

Verifying the split turned up a defect in the machinery meant to verify it, recorded as
**`KI-CG-20260826-1612`**.

Pattern C *requires* renaming every moved child, because `check_ac_limits.py` derives a child's
parent from its **ID string** rather than from `covered_by` (GE-106) — a moved child that kept
its old prefix would still count against its old parent. All six AC guardian hooks read
`git diff --cached --name-only --diff-filter=AM`. A rename is status **R**. `AM` does not
include `R`.

So the one operation most likely to break parent/child back-links produces a commit in which the
back-link gate receives none of the moved records.

This was proven rather than reasoned. `BP-100n-1` was deliberately removed from `BP-100n`'s
`covered_by` — a real violation of precisely what the hook enforces — and the hook run two ways
against that identical broken store:

| how it was invoked | result |
|---|---|
| via the git index, children staged as `R` | **exit 0**, no output |
| via `HOOK_TEST_FILES`, bypassing the filter | **exit 1**, naming the missing back-link |

Not leniency about renames — blindness to them. `git diff --cached --name-only --diff-filter=AM`
listed 4 of the 7 staged AC records; `--diff-filter=R` listed the 3 missing ones.

This is adjacent to `KI-CG-001` but distinct, and both entries stay. `KI-CG-001` is "the file was
never staged, so the hook never saw it," and staging discipline fixes it. This one is "the file
**was** staged and the hook still never saw it" — you can stage every file correctly and still get
a clean pass. The suggested fix is `--diff-filter=AMR` across the shared staged-path helpers,
where the same line has drifted into fifteen copies.

The split itself is verified despite the blind spot: rename detection was disabled locally so git
reported the moves as Add + Delete, bringing them inside the `AM` filter, and all six gates were
re-run with the moved children genuinely inspected. `check_ac_limits` was separately confirmed to
be looking at `BP-100k` at all, by adding a sixth child and watching it block at
`6 L2 children exceeds max 5`.

## Scope

No production behaviour changes. Edits to `scripts/build.py`, `scripts/build_helpers.py`,
`scripts/build_phases.py` and the three `templates/scripts/commit_guardian/` gates are
AC-ID traceability comments only — `BP-100k-6/-7/-8` renamed to `BP-100n-1/-2/-3` so a grep for a
criterion id still finds the code it motivated. Historical `amended_by` entries naming the old
ids are left verbatim, with a pointer recording the rename.

Separately, the 61 mypy errors in this epic's test files are cleared to zero, with no assertion
weakened — regex narrowing added *after* the existing `assertIsNotNone`, never replacing it, and
class-level annotations for `setUpClass` attributes. Two of the repaired assertions were
mutation-checked to confirm they still fail with their own diagnostic when the thing under test
breaks. One real bug surfaced on the way: a chained self-assignment,
`self.repo = self.repo = Path(...)`, in a hardening test's `setUp`.
