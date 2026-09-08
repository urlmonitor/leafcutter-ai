---
title: "The queue that picks what to build next says what it picks"
date: "2026-09-08"
time: "09:17"
type: manual
components:
  - ac_driven_dev
  - ac_store
summary: "Wrote 15 acceptance criteria specifying how the build system decides which task to work on next, and documented two places where the existing rules disagree with themselves — no code changed."
description: "One commit (e53f00421). Authored 15 draft ACs under ACD-400 (three L1s: ACD-400c approval gate, ACD-400d sort order, ACD-400e written account) governing scan_ac_store.py's readiness-approval filter and three-key ready-list sort, both previously unspecified. Also documents that the sort order is mis-specified, not just unspecified: two existing ACD-400a records describe a two-key sort while the shipped code and a green test both use three keys. No behaviour change, no tests, all ACs readiness: draft."
commits:
  - e53f00421
breaking: false
---

## Entry

This is an AC-authoring commit only. It adds 15 new acceptance-criteria records
to the store; it does not touch `scan_ac_store.py` or any other source file,
and it ships no tests. Every new record is `readiness: draft` — none of this
is approved, and none of it changes what the scanner does today.

### Why it exists

`scan_ac_store.py` decides which acceptance criterion the whole build system
works on next. Two of its selection rules had no acceptance criterion
governing them at all, which means a one-line edit to either would redirect
every subsequent build and nothing — no test, no gate, no review — would
object:

- **The approval gate** (`_is_approved`): only records with `readiness:
  approved` are eligible; `draft`, `reviewed`, and absent `readiness` are all
  withheld.
- **The sort order** (`_sort_ready`): ready records are ordered by three
  keys — `priority`, then `estimated_complexity`, then AC id.

This commit authors ACD-400c (the approval gate), ACD-400d (the sort order),
and ACD-400e (a true written account of current behaviour) as new L1s under
ACD-400, which already owns "a scanner identifies which leaf-level ACs are
ready," across 15 leaf criteria.

### The sharper finding: the sort order isn't merely ungoverned, it's mis-governed

ACD-400a and ACD-400a-1 both already state the sort as **two** keys —
`estimated_complexity` ascending, then AC id ascending. The shipped code
sorts on **three**, with `priority` first. A test written faithfully from
the existing store records would fail against the code; a test written from
the code contradicts the store.

That contradiction isn't merely "no test exists to catch it" — a test
already exists and is green. `test_bo2400a_fast_lane.py
::test_ac2_deterministic_sort_order` pins the three-key order today. Its two
fixtures are both `estimated_complexity: S`, which is exactly the tie that
forces the `priority` key to decide: three-key ordering returns `[011, 010]`
and the assertion passes; two-key ordering falls through to id-ascending and
returns `[010, 011]`, which would fail the same assertion. So a passing test
asserts three keys while two store records assert two, and neither side can
see the other. None of the three existing records (ACD-400a, ACD-400a-1) is
amended by this commit — ACD-400e-2 owns reconciling them and states that as
a testable condition rather than silently picking a side.

### Other findings, each verified by running the scanner rather than reading it

- **Approval is an exact string match.** `"APPROVED"` and `"approved "` with
  a trailing space are both silently withheld — treated the same as no
  readiness at all.
- **The gate is query-independent.** Three different argument combinations
  over one store, each holding records that would qualify for a different
  reason, all returned only the approved id — the broadest question a reader
  can ask still returns a silently filtered subset.
- **Withheld work is invisible everywhere, not just excluded.** A
  seven-record store with six unapproved records printed `READY (1) /
  BLOCKED (0)` — unapproved work appears in neither list and in neither
  count.
- **The two fast-lane selectors import these same two rules**, so an edit to
  either moves both selectors at once — and the selectors already disagree
  with each other: `resolve_connected_build_set` returns a draft record
  where `select_batch` does not.

### Two policy questions left open, not answered

- An unrecognised `priority` string scores 99 and sinks below `low` while
  still being offered for build — so a typo silently demotes work rather
  than rejecting it. The criteria record this as observed behaviour and
  leave the "should this be an error instead" question open for BrainCandy.
- Absent `priority` defaults generously to `medium`; absent `readiness`
  excludes the record entirely. Same "field is missing" condition, opposite
  policy, and the criteria surface the inconsistency rather than resolving
  it.

Nothing about the scanner itself changed in this commit. The next step is
review and approval of these draft criteria, then the reconciliation work
ACD-400e-2 already anticipates.
